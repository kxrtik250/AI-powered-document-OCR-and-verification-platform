# VeriSight - Intelligent Document Verification

VeriSight is a full-stack final-year project for identity and business-document verification. It accepts PDF/JPG/PNG uploads, performs OCR with image preprocessing, extracts document fields, estimates forensic risk, creates a confidence score, records an audit trail, and generates a polished PDF report.

![React](https://img.shields.io/badge/frontend-React%20%2B%20Tailwind-0f766e) ![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688) ![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-336791)

## Capabilities

- JWT registration/login and per-user document isolation
- EasyOCR with Tesseract fallback; denoise, CLAHE contrast enhancement, and deskew
- Aadhaar, PAN, passport, driving licence, invoice, and certificate classification
- Regex/normalization extraction for holder, DOB, identifier, address, issue/expiry dates
- Date/format validation and explainable OpenCV signals: blur, ELA-style recompression anomalies, potential copy-move features, text confidence dispersion
- Explainable risk scorecard, human review queue with required rationale, PDF report, and audit history/search
- Premium responsive React command centre with review control, risk distribution, and operational statistics

## Quick start

```bash
copy backend\.env.example backend\.env
# Edit backend/.env: at a minimum set SECRET_KEY, then run:
docker compose up --build
```

Visit `http://localhost:8080`. The compose configuration starts PostgreSQL, FastAPI, and Nginx-hosted React. See [docs/deployment.md](docs/deployment.md) for native development and operational configuration.

## Repository layout

```text
project/
├── frontend/       React, Tailwind, Axios, React Router UI
├── backend/        FastAPI, SQLAlchemy, OCR, forensic and report modules
├── ai_models/      Reserved local cache/mounted model directory
├── database/       Reference PostgreSQL schema
├── reports/        Generated reports (runtime data)
├── uploads/        Uploaded source documents (runtime data)
├── docs/           Architecture, API, ER diagram, deployment guide
├── tests/          API and intelligence unit tests
└── docker/         Production Dockerfiles and Nginx proxy config
```

## Verification and tests

```bash
pip install -r requirements.txt
pytest
```

The initial EasyOCR/Transformers model download can take time. The system remains functional with local Tesseract when EasyOCR cannot initialize. Set `ENABLE_TRANSFORMERS=true` to enable Hugging Face zero-shot classification for hard-to-classify documents; keep it false for predictable fully offline operation.

## Documentation

- [Architecture](docs/architecture.md)
- [ER diagram](docs/er-diagram.md)
- [API documentation](docs/api.md)
- [Deployment guide](docs/deployment.md)
- [PostgreSQL schema](database/schema.sql)

## Responsible use

The fraud score is an automated risk signal, not proof that a document is forged. Do not make adverse, legal, or identity decisions from it alone. Require a trained reviewer and validate material documents with their issuing authority.
