import logging
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _generator():
    from transformers import pipeline
    return pipeline("text2text-generation", model=get_settings().hf_explanation_model)


def generate_explanation(document_type: str, ocr_confidence: float, fraud_probability: float, findings: list[dict], fallback: str) -> str:
    """Creates a short analyst-facing explanation from a local Hugging Face model when enabled."""
    settings = get_settings()
    if not settings.enable_transformers:
        return fallback
    signals = "; ".join(f"{item['severity']}: {item['message']}" for item in findings[:4]) or "No automated forensic indicators."
    prompt = (
        "Write a neutral, concise document-verification assessment. Do not state that fraud is proven. "
        f"Document type: {document_type}. OCR confidence: {ocr_confidence:.1f}%. Fraud-risk estimate: {fraud_probability:.1f}%. "
        f"Signals: {signals}"
    )
    try:
        output = _generator()(prompt, max_new_tokens=110, do_sample=False, truncation=True)
        text = str(output[0].get("generated_text", "")).strip()
        return text or fallback
    except Exception as exc:
        logger.warning("LLM explanation unavailable; using deterministic explanation: %s", exc)
        return fallback
