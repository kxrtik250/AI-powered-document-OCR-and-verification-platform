from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class FraudAnalysis:
    findings: list[dict]
    probability: float


def _finding(code: str, severity: str, score: float, message: str, **evidence) -> dict:
    return {"code": code, "severity": severity, "score": score, "message": message, "evidence": evidence}


def analyze(images: list[np.ndarray], ocr_confidence: float, words: list[dict], preprocessing: list[dict]) -> FraudAnalysis:
    """Uses image-forensics indicators; findings are probabilistic, never proof of fraud."""
    findings: list[dict] = []
    if ocr_confidence < 45:
        findings.append(_finding("LOW_OCR_CONFIDENCE", "medium", 12, "Text recognition confidence is unusually low.", confidence=ocr_confidence))
    for item in preprocessing:
        if item["blur_score"] < 55:
            findings.append(_finding("BLURRED_IMAGE", "medium", 14, "Image contains low-detail/blurred regions that limit verification.", page=item["page"], laplacian_variance=item["blur_score"]))
        if abs(item["skew_angle"]) > 4:
            findings.append(_finding("UNUSUAL_SKEW", "low", 4, "Document has notable skew after capture.", page=item["page"], angle=item["skew_angle"]))
    for page_number, image in enumerate(images, start=1):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        # Error level analysis proxy: local JPEG recompression differences detect pasted/edited zones.
        encoded = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
        recompressed = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
        ela = cv2.absdiff(gray, recompressed)
        local_std = float(np.std(ela))
        if local_std > 12.5:
            findings.append(_finding("EDITING_ARTIFACTS", "medium", 15, "Compression artifacts vary across regions and warrant manual review.", page=page_number, ela_std=round(local_std, 2)))
        # ORB keypoint clusters flag potential copy-move only when repeated visual structures are abundant.
        keypoints, descriptors = cv2.ORB_create(nfeatures=800).detectAndCompute(gray, None)
        if descriptors is not None and len(descriptors) > 30:
            matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = sorted(matcher.match(descriptors, descriptors), key=lambda match: match.distance)
            nonself = [m for m in matches if m.queryIdx != m.trainIdx and m.distance < 18]
            if len(nonself) >= 12:
                findings.append(_finding("POSSIBLE_COPY_MOVE", "high", 22, "Repeated image features may indicate copied content; review the source document.", page=page_number, repeated_features=len(nonself)))
    confidences = [word["confidence"] for word in words]
    if confidences and np.std(confidences) > 35:
        findings.append(_finding("INCONSISTENT_TEXT_CONFIDENCE", "low", 6, "Text confidence varies sharply between regions.", standard_deviation=round(float(np.std(confidences)), 2)))
    probability = min(95.0, sum(float(item["score"]) for item in findings) * 1.15)
    return FraudAnalysis(findings=findings, probability=round(probability, 2))
