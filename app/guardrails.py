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
# 2-3 letter degree abbreviations stay case-sensitive so "be"/"ma" in prose never match.
_EDU_ABBR_RE = re.compile(
    r"(?<!\w)(?:BS|BE|MS|BA|MA|BBA|MBA|BSc|MSc|B\.Sc|FSc|ICS|Matric|Intermediate|"
    r"(?:O/A|O|A) Levels?)(?!\w)")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_YEAR_RANGE_RE = re.compile(r"\s*(?:19|20)\d{2}\s*[-\u2013]\s*(?:19|20)\d{2}\s*")
_URL_RE = re.compile(
    r"(?:https?://|www\.|(?:www\.)?(?:linkedin|github)\.com/)[^\s|,;()<>\[\]]+", re.IGNORECASE)
# Lines that are a job title, not a person ("Senior Software Engineer").
_TITLE_RE = re.compile(
    r"\b(?:engineer|developer|manager|analyst|designer|intern|lead|consultant|curriculum|vitae|"
    r"resume|architect|scientist|director|specialist|officer|executive|administrator|"
    r"coordinator|student|graduate|full\s+stack)\b", re.IGNORECASE)


def _is_edu_line(line: str) -> bool:
    return bool(_EDU_YEAR_RE.search(line) or _EDU_ABBR_RE.search(line))


# --- Pakistani identity details -------------------------------------------------------------
# Dashed CNIC (12345-1234567-1) always. A bare 13-digit number only when its line says it is an ID.
_CNIC_RE = re.compile(r"(?<!\d)(?:\d{5}-\d{7}-\d|\d{13})(?!\d)")
_CNIC_LABEL_RE = re.compile(r"\b(?:CNIC|NIC|ID card|National ID)\b", re.IGNORECASE)
# "S/O Ahmed Raza" (also D/O, W/O). Case-sensitive with a capitalised name after it, so the
# everyday "w/o" ("without") never matches. Removes from the marker to the end of the line.
_RELATION_MARK_RE = re.compile(r"\b[SDW]/O\b[:.]?[ \t]*[A-Z][^\n]*")
_RELATION_LABEL_RE = re.compile(
    r"(?im)^[ \t]*(?:father(?:'s)?[ \t]+name|husband(?:'s)?[ \t]+name|guardian)[ \t]*:[^\n]*")
_ADDR_PART_RE = re.compile(
    r"\b(House|Street|Phase|Block|Sector|Plot|Road)[ \t]*(?:No\.?|#)?[ \t]*[A-Za-z]?-?\d+[A-Za-z]?\b",
    re.IGNORECASE)
_CITY_RE = re.compile(
    r"\b(?:Lahore|Karachi|Islamabad|Rawalpindi|Faisalabad|Multan|Peshawar|Quetta|Hyderabad|Sialkot|"
    r"Gujranwala|Gujrat|Sargodha|Bahawalpur|Sukkur|Larkana|Abbottabad|Mardan|Sahiwal|Mirpur|Muzaffarabad)\b",
    re.IGNORECASE)


def _is_cnic(m: re.Match) -> bool:
    if "-" in m.group():
        return True
    text = m.string
    start = text.rfind("\n", 0, m.start()) + 1
    end = text.find("\n", m.end())
    return bool(_CNIC_LABEL_RE.search(text[start:len(text) if end < 0 else end]))


# Address rules only touch contact details: the first lines of the CV or an "Address:" line.
CONTACT_LINES = 15
_ADDR_LABEL_RE = re.compile(r"(?i)^\s*(?:home\s+address|address|residence)\s*:")
_BULLETS = ("-", "\u2022", "*", "\u2013", "\u2014", "\u00b7")


# A sentence is not an address: common sentence words or a long line rule it out.
_SENTENCE_RE = re.compile(
    r"\b(?:the|of|for|with|and|to|led|built|developed|managed|designed|worked)\b", re.IGNORECASE)
MAX_ADDRESS_WORDS = 12


def _is_address_line(line: str) -> bool:
    """House/Street/Phase/... followed by a number, plus a city, or two different such pairs."""
    if _SENTENCE_RE.search(line) or len(line.split()) > MAX_ADDRESS_WORDS:
        return False
    kinds = {m.group(1).lower() for m in _ADDR_PART_RE.finditer(line)}
    return bool(kinds) and (bool(_CITY_RE.search(line)) or len(kinds) >= 2)


def _redact_pk_lines(text: str) -> str:
    """Always-on removal of CNIC numbers, relation lines and address lines.

    Address lines are only removed in the first CONTACT_LINES non-empty lines, or when the line
    starts with "Address:" / "Home Address:" / "Residence:". Bullet lines are never address lines.
    """
    text = _CNIC_RE.sub(lambda m: "[CNIC REMOVED]" if _is_cnic(m) else m.group(), text)
    text = _RELATION_LABEL_RE.sub("[RELATION REMOVED]", text)
    text = _RELATION_MARK_RE.sub("[RELATION REMOVED]", text)
    out, seen = [], 0
    for line in text.split("\n"):
        seen += bool(line.strip())
        if line.lstrip().startswith(_BULLETS):
            out.append(line)
        elif _ADDR_LABEL_RE.match(line) or (line.strip() and seen <= CONTACT_LINES and _is_address_line(line)):
            out.append("[ADDRESS REMOVED]")
        else:
            out.append(line)
    return "\n".join(out)


def detect_pii(text: str) -> list[dict]:
    """Return a list of PII items found in *text*.

    Each item is ``{"type": "email"|"url"|"cnic"|"phone"|"year"|"name", "value": "..."}``.
    The list is ordered: emails, urls, phones, years, then name (if guessed).
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

    # LinkedIn / GitHub / personal-site links (bare domains are not detected)
    for m in _URL_RE.finditer(text):
        _add("url", m.group().rstrip(".,"))

    # CNIC (own type, so its digits are not also reported as a phone number)
    cnics = [m for m in _CNIC_RE.finditer(text) if _is_cnic(m)]
    for m in cnics:
        _add("cnic", m.group())

    # Phone numbers (filter short/long artefacts and "2019 - 2023" date ranges)
    for m in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if any(m.start() < c.end() and c.start() < m.end() for c in cnics):
            continue
        if re.fullmatch(r"[1-9]\d{12,}", m.group().strip()):
            continue  # one unbroken 13+ digit number (not starting 0 or +) is an id or a count, not a phone
        if 7 <= len(digits) <= 15 and not _YEAR_RANGE_RE.fullmatch(m.group()):
            _add("phone", m.group().strip())

    # Graduation / education years
    for line in text.splitlines():
        if _is_edu_line(line):
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
        if _TITLE_RE.search(line):
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
        elif kind == "cnic":
            cleaned = re.sub(re.escape(val), "[CNIC REMOVED]", cleaned)
        elif kind == "url":
            cleaned = re.sub(re.escape(val), "[URL REMOVED]", cleaned,
                             flags=re.IGNORECASE)
        elif kind == "year":
            # education lines only: a job's "2019 - 2023" must survive a 2019 graduation
            pattern = re.compile(r"\b" + re.escape(val) + r"\b")
            cleaned = "\n".join(pattern.sub("[YEAR REMOVED]", ln) if _is_edu_line(ln) else ln
                                for ln in cleaned.split("\n"))
    return cleaned


# PII means personal identifying information. Rules cannot find every CV layout.


def prepare_candidate(text: str, *, name: str = "", address: str = "",
                      graduation_years: tuple[int, ...] = (),
                      remove_pii: list[dict] | None = None,
                      name_optional: bool = False) -> dict[str, str]:
    """Clean supplied identity and common labelled details before scoring.

    If *remove_pii* is provided, those detected items are removed first.
    With *name_optional* a missing name is allowed: nothing is guessed or
    redacted for it (batch and confirm-pii flag such reviews for HR).
    The caller may supply *name*, *address* and *graduation_years* as
    overrides.  Review the cleaned text before sending to an external model.
    The hash identifies this normalized document, not a verified person.
    """
    if not text.strip():
        raise ValueError("Candidate text is required.")

    # If name is not supplied, try to detect it
    if name == "" and not name_optional:
        guessed = _guess_name(text)
        if guessed:
            name = guessed
    if not name.strip() and not name_optional:
        raise ValueError("Candidate name is required.")

    normalized = " ".join(text.split())
    candidate_hash = "HASH-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    # Phase 1: apply detected PII removals
    if remove_pii:
        cleaned = _remove_pii_items(text, remove_pii)
    else:
        cleaned = text

    # Phase 2: explicit name removal (if not already in remove_pii)
    if name.strip() and (not remove_pii or not any(i["type"] == "name" for i in remove_pii)):
        cleaned = re.sub(r"(?<!\w)" + re.escape(name.strip()) + r"(?!\w)",
                         "[NAME REMOVED]", cleaned, flags=re.IGNORECASE)

    # Phase 3: address removal
    if address.strip():
        cleaned = re.sub(re.escape(address.strip()), "[ADDRESS REMOVED]",
                         cleaned, flags=re.IGNORECASE)

    # Phase 4: labelled personal detail lines
    cleaned = re.sub(r"(?im)^\s*(?:name|full name|address|home address|location|"
                     r"phone|mobile|email|date of birth|dob|age|cnic|nic|national id)\s*:[^\n]*",
                     "[PERSONAL DETAIL REMOVED]", cleaned)

    # Phase 5: remaining email addresses (belt-and-suspenders)
    cleaned = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL REMOVED]", cleaned)

    # Phase 5b: CNIC numbers, relation lines (S/O, Father Name: ...) and address lines
    cleaned = _redact_pk_lines(cleaned)

    # Phase 6: education-line year removal
    lines = []
    for line in cleaned.splitlines():
        if _is_edu_line(line):
            line = re.sub(r"\b(?:19|20)\d{2}\b", "[YEAR REMOVED]", line)
        lines.append(line)
    cleaned = "\n".join(lines)

    # Phase 7: explicit graduation year removal
    for year in graduation_years:
        if type(year) is not int or not 1900 <= year <= 2099:
            raise ValueError("Graduation years must be integers from 1900 to 2099.")
        cleaned = re.sub(r"\b" + str(year) + r"\b", "[YEAR REMOVED]", cleaned)

    # Phase 8: org custom rules (e.g. location, university) — case-insensitive substring
    if remove_pii:
        # custom rules are passed as items with type/value from Settings
        for item in remove_pii:
            t = (item.get("type") or "").strip().lower()
            v = (item.get("value") or "").strip()
            if t in {"location", "university", "custom", "address", "other"} and v and len(v) >= 2:
                cleaned = re.sub(re.escape(v), "[REDACTED]", cleaned, flags=re.IGNORECASE)

    return {"candidate_hash": candidate_hash, "cleaned_text": cleaned,
            "candidate_data": wrap_candidate_data(cleaned)}


def wrap_candidate_data(text: str) -> str:
    """Escape delimiter characters; tags alone do not prevent model injection."""
    if not text.strip():
        raise ValueError("Candidate text is required.")
    return "<candidate_data>\n" + escape(text, quote=True) + "\n</candidate_data>"
