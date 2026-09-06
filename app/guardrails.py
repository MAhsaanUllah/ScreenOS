"""Small text-cleaning steps before candidate scoring."""

import hashlib
from html import escape
import re


def remove_name(text: str, name: str) -> str:
    """Replace every exact, case-sensitive occurrence of a supplied name.

    This does not detect names or remove other personal details.
    """
    name = name.strip()
    if not name:
        raise ValueError("Candidate name is required.")
    return text.replace(name, "[NAME REMOVED]")


# PII means personal identifying information. Rules cannot find every CV layout.


def prepare_candidate(text: str, *, name: str, address: str = "",
                      graduation_years: tuple[int, ...] = ()) -> dict[str, str]:
    """Clean supplied identity and common labelled details before scoring.

    The caller must supply the candidate name and any unlabelled address/year.
    Review the cleaned text before sending it to an external model.
    The hash identifies this normalized document, not a verified person.
    """
    if not text.strip():
        raise ValueError("Candidate text is required.")
    if not name.strip():
        raise ValueError("Candidate name is required.")
    normalized = " ".join(text.split())
    candidate_hash = "HASH-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cleaned = re.sub(r"(?<!\w)" + re.escape(name.strip()) + r"(?!\w)",
                     "[NAME REMOVED]", text, flags=re.IGNORECASE)
    if address.strip():
        cleaned = re.sub(re.escape(address.strip()), "[ADDRESS REMOVED]",
                         cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?im)^\s*(?:name|full name|address|home address|location|"
                     r"phone|mobile|email|date of birth|dob|age)\s*:[^\n]*",
                     "[PERSONAL DETAIL REMOVED]", cleaned)
    cleaned = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL REMOVED]", cleaned)
    # ponytail: labelled education lines only; add reviewed extraction for complex layouts.
    lines = []
    for line in cleaned.splitlines():
        if re.search(r"\b(?:graduat\w*|education|university|bachelor\w*|master\w*|"
                     r"degree|bsc|msc|phd)\b", line, re.IGNORECASE):
            line = re.sub(r"\b(?:19|20)\d{2}\b", "[YEAR REMOVED]", line)
        lines.append(line)
    cleaned = "\n".join(lines)
    for year in graduation_years:
        if type(year) is not int or not 1900 <= year <= 2099:
            raise ValueError("Graduation years must be integers from 1900 to 2099.")
        cleaned = re.sub(r"\b" + str(year) + r"\b", "[YEAR REMOVED]", cleaned)
    return {"candidate_hash": candidate_hash, "cleaned_text": cleaned,
            "candidate_data": wrap_candidate_data(cleaned)}


def wrap_candidate_data(text: str) -> str:
    """Escape delimiter characters; tags alone do not prevent model injection."""
    if not text.strip():
        raise ValueError("Candidate text is required.")
    return "<candidate_data>\n" + escape(text, quote=True) + "\n</candidate_data>"
