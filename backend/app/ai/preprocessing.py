from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PreprocessedImage:
    image: np.ndarray
    skew_angle: float
    blur_score: float


def preprocess(image: np.ndarray) -> PreprocessedImage:
    """Denoise, normalize lighting, enhance contrast, and deskew an OCR image."""
    if image is None or image.size == 0:
        raise ValueError("Image contains no pixels")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    points = np.column_stack(np.where(binary > 0))
    angle = 0.0
    if len(points) > 100:
        angle = float(cv2.minAreaRect(points[:, ::-1])[2])
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) <= 10:
            height, width = enhanced.shape
            matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
            enhanced = cv2.warpAffine(enhanced, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        else:
            angle = 0.0
    return PreprocessedImage(enhanced, round(angle, 2), float(cv2.Laplacian(enhanced, cv2.CV_64F).var()))
