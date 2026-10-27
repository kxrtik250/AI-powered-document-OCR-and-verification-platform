-- Reference PostgreSQL schema. The application creates equivalent tables on startup.
CREATE TYPE documentstatus AS ENUM ('uploaded', 'processing', 'verified', 'suspicious', 'failed');

CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  full_name VARCHAR(160) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE documents (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  original_filename VARCHAR(255) NOT NULL,
  stored_filename VARCHAR(255) NOT NULL UNIQUE,
  mime_type VARCHAR(100) NOT NULL,
  document_type VARCHAR(50) NOT NULL DEFAULT 'unknown',
  status documentstatus NOT NULL DEFAULT 'uploaded',
  extracted_text TEXT,
  ocr_confidence DOUBLE PRECISION,
  fields JSONB NOT NULL DEFAULT '{}'::jsonb,
  findings JSONB NOT NULL DEFAULT '[]'::jsonb,
  fraud_probability DOUBLE PRECISION,
  confidence_score INTEGER CHECK (confidence_score BETWEEN 0 AND 100),
  explanation TEXT,
  risk_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
  review_status VARCHAR(30) NOT NULL DEFAULT 'not_reviewed',
  review_note TEXT,
  reviewed_at TIMESTAMPTZ,
  report_path VARCHAR(500),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  verified_at TIMESTAMPTZ
);
CREATE INDEX ix_documents_owner_created ON documents(owner_id, created_at DESC);
CREATE INDEX ix_documents_status ON documents(status);
CREATE INDEX ix_documents_type ON documents(document_type);
CREATE INDEX ix_documents_review_status ON documents(review_status);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  action VARCHAR(100) NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_audit_logs_document_created ON audit_logs(document_id, created_at DESC);
