import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.document_parser import classify_document, extract_fields, validate_fields
from app.ai.explainer import generate_explanation
from app.ai.fraud_detector import analyze
from app.ai.ocr import OCRService
from app.core.config import get_settings
from app.models import AuditLog, Document, DocumentStatus, User
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def audit(self, user: User, action: str, document: Document | None = None, metadata: dict | None = None) -> None:
        self.db.add(AuditLog(user_id=user.id, document_id=document.id if document else None, action=action, metadata_json=metadata or {}))

    async def save_upload(self, user: User, upload: UploadFile) -> Document:
        if upload.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF, JPG, and PNG files are accepted")
        suffix = Path(upload.filename or "document").suffix.lower()
        if suffix not in {".pdf", ".jpg", ".jpeg", ".png"}:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File extension is not supported")
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
        if len(content) > self.settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Maximum file size is {self.settings.max_upload_mb} MB")
        magic = content[:8]
        if suffix == ".pdf" and not magic.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="File content does not match a PDF")
        if suffix in {".jpg", ".jpeg"} and not magic.startswith(b"\xff\xd8\xff"):
            raise HTTPException(status_code=400, detail="File content does not match a JPEG")
        if suffix == ".png" and not magic.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(status_code=400, detail="File content does not match a PNG")
        stored = f"{uuid.uuid4().hex}{suffix}"
        target = self.settings.upload_dir / stored
        target.write_bytes(content)
        document = Document(owner_id=user.id, original_filename=Path(upload.filename or "document").name, stored_filename=stored, mime_type=upload.content_type)
        self.db.add(document)
        self.audit(user, "document_uploaded", document, {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        self.db.commit()
        self.db.refresh(document)
        return document


    def _classifier(self):
        if not self.settings.enable_transformers:
            return None
        try:
            from transformers import pipeline
            return pipeline("zero-shot-classification", model=self.settings.hf_document_model)
        except Exception as exc:
            logger.warning("Transformer classifier unavailable: %s", exc)
            return None

    def verify(self, user: User, document: Document) -> Document:
        if document.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        document.status = DocumentStatus.processing
        self.db.commit()
        try:
            ocr = OCRService().extract(self.settings.upload_dir / document.stored_filename, document.mime_type)
            document_type = classify_document(ocr.text, self._classifier())
            fields = extract_fields(ocr.text, document_type, ocr.words)
            semantic_findings = validate_fields(fields, document_type)
            fraud = analyze(ocr.images, ocr.confidence, ocr.words, ocr.preprocessing)
            findings = semantic_findings + fraud.findings
            fraud_probability = min(99.0, fraud.probability + sum(float(f["score"]) for f in semantic_findings) * 0.8)
            # Confidence is separate from fraud likelihood: OCR certainty and forensic risk both matter.
            confidence = max(0, min(100, round(0.60 * ocr.confidence + 0.40 * (100 - fraud_probability))))
            document.document_type = document_type
            document.extracted_text = ocr.text
            document.ocr_confidence = ocr.confidence
            document.fields = fields
            document.findings = findings
            document.fraud_probability = round(fraud_probability, 2)
            document.confidence_score = confidence
            document.status = DocumentStatus.suspicious if fraud_probability >= 35 or any(f["severity"] == "high" for f in findings) else DocumentStatus.verified
            document.risk_breakdown = self._risk_breakdown(ocr.confidence, findings, fraud_probability)
            # Suspicious analyses are deliberately routed to a human decision; an
            # automated score is an indicator, never a final authenticity verdict.
            document.review_status = "pending" if document.status == DocumentStatus.suspicious else "not_reviewed"
            document.review_note = None
            document.reviewed_at = None
            document.explanation = self._explain(document)
            document.verified_at = datetime.now(timezone.utc)
            self.db.flush()
            document.report_path = str(ReportGenerator().generate(document))
            self.audit(user, "document_verified", document, {"status": document.status.value, "confidence": confidence, "fraud_probability": fraud_probability})
            self.db.commit()
            self.db.refresh(document)
            return document
        except Exception as exc:
            logger.exception("Verification failed for document %s", document.id)
            document.status = DocumentStatus.failed
            document.explanation = f"Verification failed: {str(exc)[:220]}"
            self.audit(user, "verification_failed", document, {"error": str(exc)[:300]})
            self.db.commit()
            raise HTTPException(status_code=422, detail="Document could not be processed. Check that it is a readable scan.") from exc

    @staticmethod
    def _risk_breakdown(ocr_confidence: float, findings: list[dict], fraud_probability: float) -> dict:
        """Produce a reviewer-friendly scorecard from observable checks."""
        validation_codes = {"MISSING_DOCUMENT_NUMBER", "EXPIRED_DOCUMENT"}
        validation = sum(float(item["score"]) for item in findings if item["code"] in validation_codes)
        integrity = sum(float(item["score"]) for item in findings if item["code"] not in validation_codes)
        return {
            "document_integrity": min(100, round(integrity * 2.5)),
            "field_validation": min(100, round(validation * 3.5)),
            "image_quality": max(0, round(100 - ocr_confidence)),
            "overall_risk": round(fraud_probability),
        }

    def review(self, user: User, document: Document, decision: str, note: str) -> Document:
        if document.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if document.status not in {DocumentStatus.verified, DocumentStatus.suspicious}:
            raise HTTPException(status_code=409, detail="Verify the document before recording a review")
        document.review_status = decision
        document.review_note = note.strip()
        document.reviewed_at = datetime.now(timezone.utc)
        self.audit(user, "document_reviewed", document, {"decision": decision, "note_length": len(document.review_note)})
        self.db.commit()
        self.db.refresh(document)
        return document

    def _explain(self, document: Document) -> str:
        observations = [finding["message"] for finding in document.findings]
        prefix = "Suspicious indicators were found" if document.status == DocumentStatus.suspicious else "No high-risk manipulation indicator was found"
        base = f"{prefix}. The document was classified as {document.document_type.replace('_', ' ')}. OCR confidence is {document.ocr_confidence:.1f}% and the estimated fraud risk is {document.fraud_probability:.1f}%."
        if observations:
            base += " Key review items: " + " ".join(observations[:3])
        return generate_explanation(document.document_type, document.ocr_confidence or 0, document.fraud_probability or 0, document.findings, base)

    def delete(self, user: User, document: Document) -> None:
        if document.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Document not found")
        for path in [self.settings.upload_dir / document.stored_filename, Path(document.report_path) if document.report_path else None]:
            if path and path.exists():
                path.unlink()
        self.audit(user, "document_deleted", document)
        self.db.delete(document)
        self.db.commit()

    def dashboard(self, user: User) -> dict:
        rows = self.db.scalars(select(Document).where(Document.owner_id == user.id)).all()
        total = len(rows)
        verified = sum(item.status == DocumentStatus.verified for item in rows)
        suspicious = sum(item.status == DocumentStatus.suspicious for item in rows)
        ocr_values = [item.ocr_confidence for item in rows if item.ocr_confidence is not None]
        types: dict[str, int] = {}
        statuses: dict[str, int] = {}
        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        for item in rows:
            types[item.document_type] = types.get(item.document_type, 0) + 1
            statuses[item.status.value] = statuses.get(item.status.value, 0) + 1
            risk = item.fraud_probability or 0
            risk_distribution["high" if risk >= 60 else "medium" if risk >= 25 else "low"] += 1
        recent = sorted(rows, key=lambda item: item.created_at, reverse=True)[:5]
        return {"total_documents": total, "verified_documents": verified, "suspicious_documents": suspicious, "fraud_percentage": round(suspicious / total * 100, 1) if total else 0.0, "ocr_accuracy": round(sum(ocr_values) / len(ocr_values), 1) if ocr_values else 0.0, "documents_by_type": types, "documents_by_status": statuses, "risk_distribution": risk_distribution, "manual_review_pending": sum(item.review_status == "pending" for item in rows), "reviewed_documents": sum(item.review_status in {"approved", "rejected", "needs_information"} for item in rows), "recent_documents": recent}
