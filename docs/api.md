# API documentation

Interactive OpenAPI documentation is available at `http://localhost:8000/docs` once the backend is running. Protected endpoints require `Authorization: Bearer <token>`.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/register` | Create an account with `full_name`, `email`, and password (8+ chars). |
| POST | `/login` | Get a bearer JWT. |
| GET | `/me` | Get the active account profile. |
| POST | `/upload` | Multipart `file` upload: PDF/JPG/PNG, 15 MB maximum. |
| POST | `/verify` | Run OCR/forensics with `{ "document_id": "uuid" }`. |
| GET | `/review-queue` | List risk-flagged documents that are awaiting a human decision. |
| POST | `/document/{id}/review` | Record `approved`, `rejected`, or `needs_information` with a required reviewer note. |
| GET | `/dashboard` | Return aggregate account-level analytics. |
| GET | `/history?search=...` | Search up to 100 prior documents. |
| GET | `/document/{id}` | Return a document and verification data. |
| GET | `/report/{id}` | Download its PDF report. |
| DELETE | `/document/{id}` | Delete the file, PDF, database record, and dependent audits. |
| GET | `/health` | Unauthenticated service health check. |

## Example workflow

```bash
TOKEN=$(curl -s http://localhost:8000/login -H 'content-type: application/json' \
  -d '{"email":"analyst@example.com","password":"CorrectHorseBatteryStaple1"}' | jq -r .access_token)

DOC_ID=$(curl -s http://localhost:8000/upload -H "Authorization: Bearer $TOKEN" \
  -F 'file=@sample.png' | jq -r .id)

curl -X POST http://localhost:8000/verify -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d "{\"document_id\":\"$DOC_ID\"}"
```

`fraud_probability` is an automated risk estimate in percent. It must not be used alone to deny service, make a legal finding, or label someone fraudulent.

## Review workflow

Suspicious analyses are placed in the review queue. A reviewer must add a short rationale before recording a decision; the decision, timestamp, and an audit event are retained with the document. The document response also includes `risk_breakdown`, which separates image integrity, field validation, image quality, and overall risk for a clearer explanation of the score.
