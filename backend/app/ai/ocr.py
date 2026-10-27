import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.ai.preprocessing import preprocess
from app.core.config import get_settings


logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float
    words: list[dict]
    images: list[np.ndarray]
    preprocessing: list[dict]


@lru_cache
def _easyocr_reader():
    import easyocr

    settings = get_settings()

    return easyocr.Reader(
        settings.ocr_languages.split(","),
        gpu=False,
        verbose=False,
    )


def _clean_text(text: str) -> str:
    """Normalize extracted PDF text while preserving line order."""
    lines = []

    for line in text.splitlines():
        line = " ".join(line.split())

        if line:
            lines.append(line)

    return "\n".join(lines)


def _has_useful_text(text: str) -> bool:
    """
    Determine whether a PDF contains a useful embedded text layer.

    A useful text layer should contain enough characters and
    alphabetic content to be meaningful for document parsing.
    """
    cleaned = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if len(cleaned) < 20:
        return False

    alphabetic = sum(
        character.isalpha()
        for character in cleaned
    )

    return alphabetic >= 8


def _extract_pdf_text(path: Path) -> str:
    """
    Extract embedded text from a PDF using pdftotext.

    If the PDF contains a useful text layer, this text is preferred
    over OCR because it is generally more accurate.
    """
    executable = shutil.which("pdftotext")

    if not executable:
        logger.warning(
            "pdftotext not available; falling back to image OCR"
        )
        return ""

    try:
        result = subprocess.run(
            [
                executable,
                "-layout",
                str(path),
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        text = _clean_text(
            result.stdout
        )

        if not _has_useful_text(text):
            return ""

        logger.info(
            "Useful embedded PDF text detected for %s",
            path.name,
        )

        return text

    except Exception as exc:
        logger.warning(
            "Embedded PDF text extraction failed: %s",
            exc,
        )
        return ""


def _load_images(
    path: Path,
    mime_type: str,
) -> list[np.ndarray]:
    """
    Load images from a PDF or image file.

    PDF pages are rendered at 300 DPI.
    """

    if (
        mime_type == "application/pdf"
        or path.suffix.lower() == ".pdf"
    ):
        executable = shutil.which("pdftoppm")

        if not executable:
            raise RuntimeError(
                "PDF OCR requires Poppler (pdftoppm). "
                "Install it or upload an image."
            )

        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "page"

            subprocess.run(
                [
                    executable,
                    "-f",
                    "1",
                    "-l",
                    "3",
                    "-r",
                    "300",
                    "-png",
                    str(path),
                    str(prefix),
                ],
                check=True,
                capture_output=True,
            )

            pages = sorted(
                Path(tmp).glob("page-*.png")
            )

            images = []

            for page in pages:
                image = cv2.imread(
                    str(page)
                )

                if image is not None:
                    images.append(image)

            return images

    image = cv2.imread(
        str(path)
    )

    if image is None:
        # Pillow fallback for image formats OpenCV cannot read.
        image = cv2.cvtColor(
            np.array(
                Image.open(path).convert("RGB")
            ),
            cv2.COLOR_RGB2BGR,
        )

    return [image]


def _embedded_text_words(
    text: str,
) -> list[dict]:
    """
    Convert embedded PDF text into word records.

    Embedded PDF text does not provide OCR coordinates, so
    approximate coordinates are used only for compatibility
    with the existing forensic pipeline.
    """
    words = []

    for page_no, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        for word_no, value in enumerate(
            line.split(),
            start=1,
        ):
            words.append(
                {
                    "text": value,
                    "confidence": 100.0,
                    "bbox": [
                        [word_no * 10, page_no * 20],
                        [word_no * 10 + 10, page_no * 20],
                        [word_no * 10 + 10, page_no * 20 + 10],
                        [word_no * 10, page_no * 20 + 10],
                    ],
                    "page": page_no,
                }
            )

    return words


def _process_rendered_pages(
    images: list[np.ndarray],
) -> tuple[
    list[np.ndarray],
    list[dict],
]:
    """
    Preprocess rendered pages for forensic analysis.

    This does NOT initialize EasyOCR.
    """
    rendered = []
    metadata = []

    for page_no, image in enumerate(
        images,
        start=1,
    ):
        processed = preprocess(
            image
        )

        rendered.append(
            processed.image
        )

        metadata.append(
            {
                "page": page_no,
                "skew_angle": processed.skew_angle,
                "blur_score": round(
                    processed.blur_score,
                    2,
                ),
            }
        )

    return rendered, metadata


def _ocr_images(
    images: list[np.ndarray],
) -> tuple[
    list[dict],
    list[np.ndarray],
    list[dict],
]:
    """
    Perform EasyOCR on rendered images.

    Tesseract is used as a fallback if EasyOCR fails.
    """
    all_words: list[dict] = []
    rendered: list[np.ndarray] = []
    metadata: list[dict] = []

    for page_no, image in enumerate(
        images,
        start=1,
    ):
        processed = preprocess(
            image
        )

        rendered.append(
            processed.image
        )

        metadata.append(
            {
                "page": page_no,
                "skew_angle": processed.skew_angle,
                "blur_score": round(
                    processed.blur_score,
                    2,
                ),
            }
        )

        try:
            reader = _easyocr_reader()

            results = reader.readtext(
                processed.image,
                detail=1,
                paragraph=False,
            )

            for (
                bbox,
                value,
                confidence,
            ) in results:

                if not value.strip():
                    continue

                all_words.append(
                    {
                        "text": value.strip(),
                        "confidence": float(
                            confidence
                        ) * 100,
                        "bbox": bbox,
                        "page": page_no,
                    }
                )

        except Exception as exc:
            logger.warning(
                "EasyOCR unavailable; "
                "falling back to Tesseract: %s",
                exc,
            )

            data = pytesseract.image_to_data(
                processed.image,
                output_type=pytesseract.Output.DICT,
                config="--psm 6",
            )

            for index, value in enumerate(
                data["text"]
            ):
                value = value.strip()

                if not value:
                    continue

                try:
                    confidence = float(
                        data["conf"][index]
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if confidence < 0:
                    continue

                x = int(
                    data["left"][index]
                )
                y = int(
                    data["top"][index]
                )
                w = int(
                    data["width"][index]
                )
                h = int(
                    data["height"][index]
                )

                all_words.append(
                    {
                        "text": value,
                        "confidence": confidence,
                        "bbox": [
                            [x, y],
                            [x + w, y],
                            [x + w, y + h],
                            [x, y + h],
                        ],
                        "page": page_no,
                    }
                )

    return (
        all_words,
        rendered,
        metadata,
    )


def extract_text_from_pdf(
    path: Path,
) -> str:
    """
    Public helper for directly testing PDF text extraction.
    """
    return _extract_pdf_text(path)


class OCRService:

    def extract(
        self,
        path: Path,
        mime_type: str,
    ) -> OCRResult:

        is_pdf = (
            mime_type == "application/pdf"
            or path.suffix.lower() == ".pdf"
        )

        embedded_text = ""

        # ---------------------------------------------------------
        # STEP 1: Try the PDF's embedded text layer.
        # ---------------------------------------------------------
        if is_pdf:
            embedded_text = _extract_pdf_text(
                path
            )

        # ---------------------------------------------------------
        # STEP 2: Render pages.
        #
        # We still render the PDF because the forensic detector
        # needs image data.
        # ---------------------------------------------------------
        images = _load_images(
            path,
            mime_type,
        )

        if not images:
            raise ValueError(
                "No readable pages found in document"
            )

        # ---------------------------------------------------------
        # STEP 3:
        #
        # If the PDF already contains good embedded text,
        # DO NOT initialize EasyOCR.
        #
        # This prevents unnecessary EasyOCR downloads and gives
        # much better text extraction for digitally generated PDFs.
        # ---------------------------------------------------------
        if is_pdf and _has_useful_text(
            embedded_text
        ):
            text = embedded_text

            words = _embedded_text_words(
                embedded_text
            )

            confidence = 100.0

            rendered, metadata = (
                _process_rendered_pages(
                    images
                )
            )

            logger.info(
                "Using embedded PDF text for %s",
                path.name,
            )

        # ---------------------------------------------------------
        # STEP 4:
        #
        # Otherwise use normal image OCR.
        # ---------------------------------------------------------
        else:
            (
                words,
                rendered,
                metadata,
            ) = _ocr_images(
                images
            )

            text = " ".join(
                item["text"]
                for item in words
            )

            confidence = (
                sum(
                    item["confidence"]
                    for item in words
                )
                / len(words)
                if words
                else 0.0
            )

        # ---------------------------------------------------------
        # STEP 5: Return unified OCR result.
        # ---------------------------------------------------------
        return OCRResult(
            text=text,
            confidence=round(
                confidence,
                2,
            ),
            words=words,
            images=rendered,
            preprocessing=metadata,
        )