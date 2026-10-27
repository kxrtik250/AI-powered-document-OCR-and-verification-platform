import re
from datetime import date

from dateutil import parser as date_parser


DOCUMENT_PATTERNS = {
    "aadhaar": r"\b\d{4}\s?\d{4}\s?\d{4}\b|aadhaar|uidai",
    "pan": r"\b[A-Z]{5}\d{4}[A-Z]\b|permanent account number",
    "passport": r"\b[A-Z][0-9]{7}\b|passport",
    "driving_license": r"\b[A-Z]{2}\d{2}[ -]?\d{11,13}\b|driving licence|driving license",
    "invoice": r"invoice|gstin|tax invoice|bill to",
    "certificate": r"certificate|certifies that|certified",
}

DATE_PATTERN = (
    r"\b(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|"
    r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|"
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}"
    r")\b"
)


def classify_document(text: str, transformer_classifier=None) -> str:
    content = text.lower()

    matches = {
        kind: len(re.findall(pattern, content, flags=re.I))
        for kind, pattern in DOCUMENT_PATTERNS.items()
    }

    likely, count = max(matches.items(), key=lambda item: item[1])

    if count:
        return likely

    if transformer_classifier:
        labels = [
            "aadhaar card",
            "PAN card",
            "passport",
            "driving license",
            "invoice",
            "certificate",
        ]

        answer = transformer_classifier(
            text[:1500],
            candidate_labels=labels,
        )

        return answer["labels"][0].replace(" ", "_")

    return "unknown"


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.I | re.M)

    if match:
        return match.group(1).strip(" :-")

    return None


def _dates(text: str) -> list[str]:
    found = []

    for raw in re.findall(DATE_PATTERN, text, flags=re.I):
        try:
            found.append(
                date_parser.parse(
                    raw,
                    dayfirst=True,
                ).date().isoformat()
            )
        except (ValueError, OverflowError):
            continue

    return list(dict.fromkeys(found))


def _word_lines(words: list[dict] | None) -> list[str]:
    """
    Reconstruct OCR words into approximate visual lines using
    their bounding-box Y positions.
    """
    if not words:
        return []

    items = []

    for word in words:
        value = str(word.get("text", "")).strip()
        bbox = word.get("bbox")

        if not value or not bbox:
            continue

        try:
            ys = [float(point[1]) for point in bbox]
            xs = [float(point[0]) for point in bbox]

            center_y = sum(ys) / len(ys)
            min_x = min(xs)

            items.append(
                {
                    "text": value,
                    "y": center_y,
                    "x": min_x,
                }
            )
        except (TypeError, ValueError, IndexError):
            continue

    if not items:
        return []

    # Sort approximately top-to-bottom.
    items.sort(key=lambda item: item["y"])

    lines: list[list[dict]] = []
    y_tolerance = 18.0

    for item in items:
        placed = False

        for line in lines:
            average_y = sum(x["y"] for x in line) / len(line)

            if abs(item["y"] - average_y) <= y_tolerance:
                line.append(item)
                placed = True
                break

        if not placed:
            lines.append([item])

    result = []

    for line in lines:
        line.sort(key=lambda item: item["x"])
        result.append(" ".join(item["text"] for item in line))

    return result


def _pan_name_from_words(
    words: list[dict] | None,
    dob: str | None,
) -> str | None:
    """
    Extract PAN holder name from OCR lines.

    Typical PAN OCR layout:

        INCOME TAX DEPARTMENT
        GOVT OF INDIA
        PERSON NAME
        FATHER NAME
        14/05/1995
        Permanent Account Number
        XXXXX1234X

    The line immediately above the DOB is normally the father's
    name, while the line above that is normally the card holder's name.
    """

    if not words or not dob:
        return None

    lines = _word_lines(words)

    if not lines:
        return None

    ignored = {
        "income tax department",
        "govt of india",
        "government of india",
        "permanent account number",
        "signature",
    }

    # Find the line containing the DOB.
    dob_index = None

    for index, line in enumerate(lines):
        if re.search(DATE_PATTERN, line, flags=re.I):
            dob_index = index
            break

    if dob_index is None:
        return None

    candidates = []

    # Look at the two lines immediately before DOB.
    for index in range(dob_index - 1, max(-1, dob_index - 4), -1):
        candidate = lines[index].strip()

        if not candidate:
            continue

        if candidate.lower() in ignored:
            continue

        # Remove obvious PAN headings/noise.
        if re.search(
            r"income\s+tax|govt|government|permanent\s+account|signature",
            candidate,
            flags=re.I,
        ):
            continue

        # Remove PAN number if it somehow occurs on the line.
        candidate = re.sub(
            r"\b[A-Z]{5}\d{4}[A-Z]\b",
            "",
            candidate,
            flags=re.I,
        ).strip()

        if not re.fullmatch(
            r"[A-Za-z]+(?:\s+[A-Za-z]+){1,5}",
            candidate,
        ):
            continue

        candidates.append(candidate)

    # With a normal PAN layout, the first candidate is usually the
    # father's name and the second candidate is the holder's name.
    if len(candidates) >= 2:
        return candidates[1]

    if candidates:
        return candidates[0]

    return None


def _pan_fallback_name(
    text: str,
    dob: str | None,
) -> str | None:
    """
    Fallback for flattened OCR text when word positions are unavailable.
    """

    if not dob:
        return None

    normalized = re.sub(r"\s+", " ", text).strip()

    # Remove common headings.
    for pattern in [
        r"\bINCOME\s+TAX\s+DEPARTMENT\b",
        r"\bGOVT(?:ERNMENT)?\s+OF\s+INDIA\b",
        r"\bPERMANENT\s+ACCOUNT\s+NUMBER\b",
        r"\bSIGNATURE\b",
    ]:
        normalized = re.sub(
            pattern,
            " ",
            normalized,
            flags=re.I,
        )

    normalized = re.sub(
        r"\b[A-Z]{5}\d{4}[A-Z]\b",
        " ",
        normalized,
        flags=re.I,
    )

    normalized = re.sub(r"\s+", " ", normalized).strip()

    dob_match = re.search(
        DATE_PATTERN,
        normalized,
        flags=re.I,
    )

    if not dob_match:
        return None

    before_dob = normalized[:dob_match.start()].strip()
    words = before_dob.split()

    ignored = {
        "income",
        "tax",
        "department",
        "govt",
        "government",
        "of",
        "india",
        "permanent",
        "account",
        "number",
        "signature",
    }

    clean_words = []

    for word in words:
        cleaned = re.sub(r"[^A-Za-z]", "", word)

        if not cleaned:
            continue

        if cleaned.lower() in ignored:
            continue

        clean_words.append(cleaned)

    # Fallback only. Prefer two-word names.
    if len(clean_words) >= 2:
        return " ".join(clean_words[-2:])

    return None


def extract_fields(
    text: str,
    document_type: str,
    words: list[dict] | None = None,
) -> dict[str, str | list[str] | None]:

    compact = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    dates = _dates(compact)

    patterns = {
        "pan": r"\b([A-Z]{5}\d{4}[A-Z])\b",
        "aadhaar": r"\b(\d{4}\s?\d{4}\s?\d{4})\b",
        "passport": r"\b([A-Z][0-9]{7})\b",
        "driving_license": r"\b([A-Z]{2}\d{2}[ -]?\d{11,13})\b",
        "invoice": r"(?:invoice\s*(?:no|number|#)\s*[:.-]?\s*)([A-Z0-9/-]+)",
    }

    # Standard labelled name extraction.
    name = _first_match(
        r"(?:name|holder|applicant)\s*[:.-]?\s*([A-Z][A-Za-z .]{2,70})",
        compact,
    )

    if name:
        name = re.sub(
            r"\s+[A-Z]{2,}$",
            "",
            name,
        ).strip()

    # Address.
    address = _first_match(
        r"(?:address)\s*[:.-]?\s*([A-Za-z0-9,./() -]{8,160})",
        compact,
    )

    # DOB with an explicit label.
    dob = _first_match(
        r"(?:dob|date of birth|birth)\s*[:.-]?\s*("
        + DATE_PATTERN
        + r")",
        compact,
    )

    # PAN cards often have an unlabeled DOB.
    if document_type == "pan" and not dob and dates:
        dob = dates[0]

    # PAN name: first use visual OCR lines.
    if document_type == "pan" and not name:
        name = _pan_name_from_words(
            words,
            dob,
        )

    # Final fallback if OCR positions are unavailable.
    if document_type == "pan" and not name:
        name = _pan_fallback_name(
            compact,
            dob,
        )

    issue_date = _first_match(
        r"(?:issue date|date of issue|issued)\s*[:.-]?\s*("
        + DATE_PATTERN
        + r")",
        compact,
    )

    expiry_date = _first_match(
        r"(?:expiry date|valid (?:until|upto)|date of expiry|expires)\s*[:.-]?\s*("
        + DATE_PATTERN
        + r")",
        compact,
    )

    number = _first_match(
        patterns.get(document_type, r"$^"),
        compact,
    )

    return {
        "name": name,
        "date_of_birth": dob,
        "document_number": number,
        "address": address,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "detected_dates": dates,
    }


def validate_fields(
    fields: dict,
    document_type: str,
) -> list[dict]:

    findings: list[dict] = []

    number = fields.get("document_number")

    if (
        document_type
        in {
            "aadhaar",
            "pan",
            "passport",
            "driving_license",
        }
        and not number
    ):
        findings.append(
            {
                "code": "MISSING_DOCUMENT_NUMBER",
                "severity": "high",
                "score": 20,
                "message": "Expected document number was not found.",
                "evidence": {
                    "document_type": document_type,
                },
            }
        )

    expiry = fields.get("expiry_date")

    if expiry:
        try:
            if (
                date_parser.parse(
                    expiry,
                    dayfirst=True,
                ).date()
                < date.today()
            ):
                findings.append(
                    {
                        "code": "EXPIRED_DOCUMENT",
                        "severity": "medium",
                        "score": 12,
                        "message": "The document appears expired.",
                        "evidence": {
                            "expiry_date": expiry,
                        },
                    }
                )
        except (ValueError, OverflowError):
            pass

    return findings