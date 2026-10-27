from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    # bcrypt's input limit is 72 bytes; reject longer secrets instead of silently truncating them.
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    model_config = {"from_attributes": True}


class FindingResponse(BaseModel):
    code: str
    severity: str
    score: float
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    id: UUID
    original_filename: str
    document_type: str
    status: str
    ocr_confidence: float | None
    fraud_probability: float | None
    confidence_score: int | None
    fields: dict[str, Any]
    findings: list[FindingResponse]
    explanation: str | None
    risk_breakdown: dict[str, Any]
    review_status: str
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    verified_at: datetime | None
    model_config = {"from_attributes": True}


class DocumentSummary(BaseModel):
    id: UUID
    original_filename: str
    document_type: str
    status: str
    confidence_score: int | None
    fraud_probability: float | None
    review_status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    total_documents: int
    verified_documents: int
    suspicious_documents: int
    fraud_percentage: float
    ocr_accuracy: float
    documents_by_type: dict[str, int]
    documents_by_status: dict[str, int]
    risk_distribution: dict[str, int]
    manual_review_pending: int
    reviewed_documents: int
    recent_documents: list[DocumentSummary]


class VerifyRequest(BaseModel):
    document_id: UUID


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|needs_information)$")
    note: str = Field(min_length=2, max_length=1200)
