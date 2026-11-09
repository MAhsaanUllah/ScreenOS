"""Read PDF, DOCX and UTF-8 TXT resumes without changing their wording."""

import argparse
from pathlib import Path
import re
import sys

import pdfplumber
from docx import Document
from docx.table import Table


def _is_white(color) -> bool:
    if isinstance(color, (int, float)):
        color = (color,)
    if not isinstance(color, (tuple, list)) or not color:
        return False
    if len(color) == 4:  # CMYK: no ink
        return all(c <= 0.05 for c in color)
    return len(color) in (1, 3) and all(c >= 0.95 for c in color)


def _visible(region):
    """Drop text a reader cannot see: under 5pt, or white and not on a coloured box.

    shortcut: white text over a background *image* looks the same as hidden text and is dropped.
    """
    boxes = [r for r in region.rects if r.get("fill") and not _is_white(r.get("non_stroking_color"))]

    def keep(obj):
        if obj["object_type"] != "char":
            return True
        if obj["size"] < 5:
            return False
        if _is_white(obj.get("non_stroking_color")):
            x, y = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
            return any(r["x0"] <= x <= r["x1"] and r["top"] <= y <= r["bottom"] for r in boxes)
        return True
    return region.filter(keep)


def _gutter(words: list[dict], width: float) -> float | None:
    """x of an empty vertical strip with real text on both sides, else None (single column).

    shortcut: a line that crosses the strip (full-width header) hides it, so such pages are
    read the old way; handle bands only if that shows up in real CVs.
    """
    if len(words) < 20:
        return None
    covered = bytearray(int(width) + 2)
    for w in words:
        for x in range(int(w["x0"]), int(w["x1"]) + 1):
            covered[x] = 1
    best, x = None, int(width * 0.15)
    while x < int(width * 0.85):
        if covered[x]:
            x += 1
            continue
        start = x
        while x < int(width * 0.85) and not covered[x]:
            x += 1
        mid = (start + x) / 2
        left = sum(1 for w in words if w["x1"] <= mid)
        right = sum(1 for w in words if w["x0"] >= mid)
        if x - start >= 10 and min(left, right) >= max(15, 0.1 * len(words)) and (best is None or x - start > best[0]):
            best = (x - start, mid)
    return best[1] if best else None


def _glyphs(region) -> int:
    return sum(1 for c in region.chars if not c["text"].isspace())


def _page_text(page) -> tuple[str, int]:
    """(text, number of hidden characters dropped). The dropped text itself is never kept."""
    visible = _visible(page)
    gone = _glyphs(page) - _glyphs(visible)
    mid = _gutter(visible.extract_words(), page.width)
    if mid is None:
        return visible.extract_text() or "", gone
    columns = [_visible(page.crop(box)).extract_text() or ""
               for box in ((0, 0, mid, page.height), (mid, 0, page.width, page.height))]
    return "\n".join(c for c in columns if c.strip()), gone


def extract_text(file_path: str | Path) -> str:
    """Return readable text or raise ValueError with a useful explanation."""
    return extract_with_report(file_path)[0]


def extract_with_report(file_path: str | Path) -> tuple[str, int]:
    """Like extract_text, plus how many characters of hidden PDF text were dropped."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise ValueError("Choose a PDF, DOCX or TXT file.")
    if not path.is_file():
        raise ValueError("File not found. Check the file path.")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("File is too large. Use a file under 10 MB.")

    hidden = 0
    try:
        if suffix == ".txt":
            raw = path.read_text(encoding="utf-8-sig")
        elif suffix == ".pdf":
            with pdfplumber.open(path) as pdf:
                pages = []
                for page in pdf.pages:
                    text, gone = _page_text(page)
                    hidden += gone
                    if not text.strip():
                        # Optional OCR fallback for scanned PDFs (needs tesseract + pytesseract)
                        try:
                            # ponytail: OCR only if libs + binary present, else keep strict error
                            import pytesseract  # type: ignore
                            from PIL import Image  # type: ignore

                            # render page to image via pdfplumber if available
                            try:
                                im = page.to_image(resolution=300).original  # PIL Image
                                ocr = pytesseract.image_to_string(im) or ""
                                if ocr.strip():
                                    text = ocr
                                else:
                                    raise ValueError("empty ocr")
                            except Exception:
                                raise
                        except Exception:
                            raise ValueError(
                                "A PDF page has no readable text. It may be blank or scanned. "
                                "Export as text-based PDF/DOCX/TXT, or install Tesseract OCR (pytesseract) for scanned PDFs."
                            ) from None
                    pages.append(text)
            raw = "\n\n".join(pages)
        else:
            parts = []
            for block in Document(path).iter_inner_content():
                if isinstance(block, Table):
                    parts.extend(" | ".join(cell.text for cell in row.cells)
                                 for row in block.rows)
                else:
                    parts.append(block.text)
            raw = "\n".join(parts)
    except UnicodeError as exc:
        raise ValueError("Save the TXT file using UTF-8 encoding and try again.") from exc
    except Exception as exc:
        # File readers use different exceptions for damaged or locked documents.
        raise ValueError(f"Could not read {path.name}: {exc}") from exc

    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in raw.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not text:
        raise ValueError("No readable text found. Provide a non-empty resume.")
    return text, hidden


def main() -> int:
    parser = argparse.ArgumentParser(description="Read text from a resume.")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        print(extract_text(args.file))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
