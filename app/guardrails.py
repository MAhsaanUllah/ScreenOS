"""Small text-cleaning steps before candidate scoring."""

import hashlib
from html import escape
import re


# ---------------------------------------------------------------------------
# PII detection — rule-based; cannot find every CV layout.
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?"             # optional country code
    r"(?:\(?\d{2,4}\)?[\s\-]?)"           # area code
    r"\d{3,4}[\s\-]?\d{3,4}"              # local number
)
_EDU_YEAR_RE = re.compile(
    r"\b(?:graduat\w*|education|university|bachelor\w*|master\w*|"
    r"degree|bsc|msc|phd)\b", re.IGNORECASE
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def detect_pii(text: str) -> list[dict]:
    """Return a list of PII items found in *text*.

    Each item is ``{"type": "email"|"phone"|"year"|"name", "value": "..."}``.
    The list is ordered: emails, phones, years, then name (if guessed).
    Duplicates are collapsed.
    """
    items: list[dict] = []
    seen: set[str] = set()

    def _add(kind: str, val: str) -> None:
        key = f"{kind}:{val.lower()}"
        if key not in seen:
            seen.add(key)
            items.append({"type": kind, "value": val})

    # Emails
    for m in _EMAIL_RE.finditer(text):
        _add("email", m.group())

    # Phone numbers (filter short/long artefacts)
    for m in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 7 <= len(digits) <= 15:
            _add("phone", m.group().strip())

    # Graduation / education years
    for line in text.splitlines():
        if _EDU_YEAR_RE.search(line):
            for y in _YEAR_RE.finditer(line):
                _add("year", y.group())

    # Name guess from header
    name = _guess_name(text)
    if name:
        _add("name", name)

    return items


def _guess_name(text: str) -> str | None:
    """Heuristic: extract the most likely candidate name from a CV header.

    Checks for a ``Name: ...`` label first, then the first non-empty line
    if it looks like a personal name (short, mostly letters/spaces, title-cased).
    """
    for line in text.splitlines()[:15]:
        m = re.match(r"(?:full\s+)?name\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
    for line in text.splitlines()[:5]:
        line = line.strip()
        if not line or len(line) > 80:
            continue
        words = line.split()
        if 2 <= len(words) <= 6 and all(w[0:1].isupper() or w.isupper() for w in words if len(w) > 1):
            if re.fullmatch(r"[A-Za-z\s\-'.]+", line):
                return line
    return None


# ---------------------------------------------------------------------------
# PII removal
# ---------------------------------------------------------------------------

def remove_name(text: str, name: str) -> str:
    """Replace every exact, case-insensitive occurrence of a supplied name."""
    name = name.strip()
    if not name:
        raise ValueError("Candidate name is required.")
    return re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)",
                  "[NAME REMOVED]", text, flags=re.IGNORECASE)


def _remove_pii_items(text: str, items: list[dict]) -> str:
    """Apply removals for a list of detected PII items."""
    cleaned = text
    for item in items:
        kind = item["type"]
        val = item["value"]
        if kind == "name":
            cleaned = re.sub(r"(?<!\w)" + re.escape(val) + r"(?!\w)",
                             "[NAME REMOVED]", cleaned, flags=re.IGNORECASE)
        elif kind == "email":
            cleaned = re.sub(re.escape(val), "[EMAIL REMOVED]", cleaned,
                             flags=re.IGNORECASE)
        elif kind == "phone":
            cleaned = re.sub(re.escape(val), "[PHONE REMOVED]", cleaned,
                             flags=re.IGNORECASE)
        elif kind == "year":
            cleaned = re.sub(r"\b" + re.escape(val) + r"\b",
                             "[YEAR REMOVED]", cleaned)
    return cleaned


# PII means personal identifying information. Rules cannot find every CV layout.


def prepare_candidate(text: str, *, name: str = "", address: str = "",
                      graduation_years: tuple[int, ...] = (),
                      remove_pii: list[dict] | None = None) -> dict[str, str]:
    """Clean supplied identity and common labelled details before scoring.

    If *remove_pii* is provided, those detected items are removed first.
    The caller may supply *name*, *address* and *graduation_years* as
    overrides.  Review the cleaned text before sending to an external model.
    The hash identifies this normalized document, not a verified person.
    """
    if not text.strip():
        raise ValueError("Candidate text is required.")

    # If name is not supplied, try to detect it
    if name == "":
        guessed = _guess_name(text)
        if guessed:
            name = guessed
    if not name.strip():
        raise ValueError("Candidate name is required.")

    normalized = " ".join(text.split())
    candidate_hash = "HASH-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    # Phase 1: apply detected PII removals
    if remove_pii:
        cleaned = _remove_pii_items(text, remove_pii)
    else:
        cleaned = text

    # Phase 2: explicit name removal (if not already in remove_pii)
    if not remove_pii or not any(i["type"] == "name" for i in remove_pii):
        cleaned = re.sub(r"(?<!\w)" + re.escape(name.strip()) + r"(?!\w)",
                         "[NAME REMOVED]", cleaned, flags=re.IGNORECASE)

    # Phase 3: address removal
    if address.strip():
        cleaned = re.sub(re.escape(address.strip()), "[ADDRESS REMOVED]",
                         cleaned, flags=re.IGNORECASE)

    # Phase 4: labelled personal detail lines
    cleaned = re.sub(r"(?im)^\s*(?:name|full name|address|home address|location|"
                     r"phone|mobile|email|date of birth|dob|age)\s*:[^\n]*",
                     "[PERSONAL DETAIL REMOVED]", cleaned)

    # Phase 5: remaining email addresses (belt-and-suspenders)
    cleaned = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL REMOVED]", cleaned)

    # Phase 6: education-line year removal
    lines = []
    for line in cleaned.splitlines():
        if re.search(r"\b(?:graduat\w*|education|university|bachelor\w*|master\w*|"
                     r"degree|bsc|msc|phd)\b", line, re.IGNORECASE):
            line = re.sub(r"\b(?:19|20)\d{2}\b", "[YEAR REMOVED]", line)
        lines.append(line)
    cleaned = "\n".join(lines)

    # Phase 7: explicit graduation year removal
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
