"""Read PDF, DOCX and UTF-8 TXT resumes without changing their wording."""

import argparse
from pathlib import Path
import re
import sys

import pdfplumber
from docx import Document
from docx.table import Table


def extract_text(file_path: str | Path) -> str:
    """Return readable text or raise ValueError with a useful explanation."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise ValueError("Choose a PDF, DOCX or TXT file.")
    if not path.is_file():
        raise ValueError("File not found. Check the file path.")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("File is too large. Use a file under 10 MB.")

    try:
        if suffix == ".txt":
            raw = path.read_text(encoding="utf-8-sig")
        elif suffix == ".pdf":
            with pdfplumber.open(path) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
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
    return text


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
