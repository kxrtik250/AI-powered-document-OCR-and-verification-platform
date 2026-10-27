def test_register_login_and_authenticated_dashboard(client):
    response = client.post("/register", json={"full_name": "Ada Lovelace", "email": "ada@example.com", "password": "CorrectHorseBatteryStaple1"})
    assert response.status_code == 201
    token = client.post("/login", json={"email": "ada@example.com", "password": "CorrectHorseBatteryStaple1"}).json()["access_token"]
    dashboard = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dashboard.status_code == 200
    assert dashboard.json()["total_documents"] == 0
    assert dashboard.json()["manual_review_pending"] == 0
    assert dashboard.json()["risk_distribution"] == {"low": 0, "medium": 0, "high": 0}


def test_rejects_unauthenticated_upload(client):
    response = client.post("/upload", files={"file": ("x.png", b"not-an-image", "image/png")})
    assert response.status_code == 401


def test_reviewer_can_record_decision_for_pending_document(client):
    from app.db.session import SessionLocal
    from app.models import Document, DocumentStatus, User

    client.post("/register", json={"full_name": "Grace Hopper", "email": "grace@example.com", "password": "CorrectHorseBatteryStaple1"})
    token = client.post("/login", json={"email": "grace@example.com", "password": "CorrectHorseBatteryStaple1"}).json()["access_token"]
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email="grace@example.com").one()
        document = Document(owner_id=user.id, original_filename="scan.png", stored_filename="scan-test.png", mime_type="image/png", status=DocumentStatus.suspicious, review_status="pending", confidence_score=48, fraud_probability=61.0)
        db.add(document)
        db.commit()
        document_id = document.id
    finally:
        db.close()
    response = client.post(f"/document/{document_id}/review", headers={"Authorization": f"Bearer {token}"}, json={"decision": "needs_information", "note": "The security mark is not readable in this scan."})
    assert response.status_code == 200
    assert response.json()["review_status"] == "needs_information"
