import os

os.environ["DATABASE_URL"] = "sqlite:///./test_verisight.db"
os.environ["UPLOAD_DIR"] = "./test_uploads"
os.environ["REPORT_DIR"] = "./test_reports"
os.environ["SECRET_KEY"] = "test-secret-key-for-verisight-application"

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
