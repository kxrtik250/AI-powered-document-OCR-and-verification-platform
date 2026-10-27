from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import Document, User
from app.schemas.api import DashboardResponse, DocumentResponse, LoginRequest, RegisterRequest, ReviewRequest, TokenResponse, UserResponse, VerifyRequest
from app.services.document_service import DocumentService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Email address is already registered")
    user = User(email=payload.email.lower(), full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, tags=["Authentication"])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserResponse, tags=["Authentication"])
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, tags=["Documents"])
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Document:
    return await DocumentService(db).save_upload(current_user, file)


def _owned_document(db: Session, user: User, document_id: UUID) -> Document:
    document = db.get(Document, document_id)
    if not document or document.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/verify", response_model=DocumentResponse, tags=["Verification"])
def verify_document(payload: VerifyRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Document:
    return DocumentService(db).verify(current_user, _owned_document(db, current_user, payload.document_id))


@router.post("/verify/{document_id}", response_model=DocumentResponse, tags=["Verification"], include_in_schema=False)
def verify_document_path(document_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Document:
    return DocumentService(db).verify(current_user, _owned_document(db, current_user, document_id))


@router.post("/document/{document_id}/review", response_model=DocumentResponse, tags=["Review"])
def review_document(document_id: UUID, payload: ReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Document:
    return DocumentService(db).review(current_user, _owned_document(db, current_user, document_id), payload.decision, payload.note)


@router.get("/review-queue", response_model=list[DocumentResponse], tags=["Review"])
def review_queue(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Document]:
    query = select(Document).where(Document.owner_id == current_user.id, Document.review_status == "pending")
    return list(db.scalars(query.order_by(Document.fraud_probability.desc(), Document.created_at.desc()).limit(limit)))


@router.get("/history", response_model=list[DocumentResponse], tags=["Documents"])
def history(search: str | None = Query(default=None, max_length=120), limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Document]:
    query = select(Document).where(Document.owner_id == current_user.id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Document.original_filename.ilike(pattern), Document.document_type.ilike(pattern), Document.extracted_text.ilike(pattern)))
    return list(db.scalars(query.order_by(Document.created_at.desc()).limit(limit)))


@router.get("/document/{document_id}", response_model=DocumentResponse, tags=["Documents"])
def get_document(document_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Document:
    return _owned_document(db, current_user, document_id)


@router.get("/report/{document_id}", tags=["Reports"])
def get_report(document_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FileResponse:
    document = _owned_document(db, current_user, document_id)
    path = Path(document.report_path or "")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Verification report is not available; verify the document first")
    return FileResponse(path, media_type="application/pdf", filename=f"verification-report-{document.id}.pdf")


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Documents"])
def delete_document(document_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    DocumentService(db).delete(current_user, _owned_document(db, current_user, document_id))


@router.get("/dashboard", response_model=DashboardResponse, tags=["Dashboard"])
def dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return DocumentService(db).dashboard(current_user)
