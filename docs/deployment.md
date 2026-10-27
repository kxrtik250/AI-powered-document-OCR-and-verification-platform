# Deployment guide

## Docker deployment

1. Copy `backend/.env.example` to `backend/.env` and set a cryptographically strong `SECRET_KEY`.
2. Review `CORS_ORIGINS`; for the supplied compose stack it must include `http://localhost:8080`.
3. Start the stack:

   ```bash
   docker compose up --build -d
   ```

4. Open `http://localhost:8080`; the API is served internally through `/api`, and API docs are reachable at `http://localhost:8080/api/docs`.

Use `docker compose logs -f backend` for OCR/errors and `docker compose down` to stop. Add `-v` only when intentionally deleting PostgreSQL and document data.

## Native development

Backend:

```bash
cd backend
copy .env.example .env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Install Tesseract and Poppler (`pdftoppm`) on the host for the fallback and PDF OCR. Frontend:

```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

## Operational hardening

- HTTPS, secure cookies if switching to cookie auth, a real secret manager, database backups, and a virus scanner are mandatory for a public deployment.
- Store files in a private, encrypted object store rather than the local volume. Enforce retention periods appropriate to your jurisdiction.
- Use Alembic migrations and a task queue for high-volume OCR. Record model versions and evaluation metrics before relying on scores operationally.
