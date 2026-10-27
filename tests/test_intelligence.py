import numpy as np

from app.ai.document_parser import classify_document, extract_fields, validate_fields
from app.ai.fraud_detector import analyze


def test_pan_classification_and_field_extraction():
    text = "INCOME TAX DEPARTMENT Permanent Account Number Name: Ada Lovelace ABCDE1234F Date of Birth: 10/12/1815"
    assert classify_document(text) == "pan"
    fields = extract_fields(text, "pan")
    assert fields["document_number"] == "ABCDE1234F"
    assert fields["name"] == "Ada Lovelace"
    assert not validate_fields(fields, "pan")


def test_forensic_analysis_flags_blurry_image():
    image = np.full((300, 500), 128, dtype=np.uint8)
    outcome = analyze([image], 90.0, [{"confidence": 90.0}], [{"page": 1, "blur_score": 1.0, "skew_angle": 0.0}])
    assert any(finding["code"] == "BLURRED_IMAGE" for finding in outcome.findings)
    assert outcome.probability > 0
