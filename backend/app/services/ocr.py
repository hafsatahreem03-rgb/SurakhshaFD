"""Real OCR using Tesseract (pytesseract), with PyMuPDF for PDFs and Pillow for images.

The engine reads words + per-word confidence, rebuilds text rows, then looks for labelled FDR
fields ("FDR No.", "Principal Amount", "Date of Maturity", ...). A field that cannot be read
reliably is returned as `needs_review` instead of being guessed.
"""
import io
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageOps

from ..config import settings

FIELD_NAMES = [
    "institution_name", "bank_name", "branch_name", "fdr_number", "account_holder",
    "principal_amount", "issue_date", "maturity_date", "interest_rate",
]

FIELD_LABELS = {
    "institution_name": "Institution name",
    "bank_name": "Bank name",
    "branch_name": "Branch name",
    "fdr_number": "FDR number",
    "account_holder": "Account holder",
    "principal_amount": "Principal amount",
    "issue_date": "Issue date",
    "maturity_date": "Maturity date",
    "interest_rate": "Interest rate",
}

# Label patterns, most specific first. Matching is case-insensitive.
LABEL_PATTERNS: dict[str, list[str]] = {
    "institution_name": [r"name\s+of\s+(the\s+)?institution", r"institution\s*name", r"in\s+favou?r\s+of", r"institution"],
    "bank_name": [r"name\s+of\s+(the\s+)?bank", r"bank\s*name", r"issuing\s+bank"],
    "branch_name": [r"branch\s*name", r"branch"],
    "fdr_number": [r"f\.?\s?d\.?\s?r\.?\s*(no|number|num)\b\.?", r"\bfd\s*(no|number)\b\.?", r"receipt\s*(no|number)\b\.?", r"deposit\s*(no|number)\b\.?"],
    "account_holder": [r"account\s*holder(\s*name)?", r"name\s+of\s+(the\s+)?depositor", r"depositor('?s)?\s*name", r"in\s+the\s+name\s+of"],
    "principal_amount": [r"principal\s*amount", r"deposit\s*amount", r"amount\s+of\s+deposit", r"principal", r"(?<!maturity\s)amount"],
    "issue_date": [r"date\s+of\s+issue", r"issue\s*date", r"date\s+of\s+deposit", r"deposit\s*date", r"value\s*date"],
    "maturity_date": [r"date\s+of\s+maturity", r"maturity\s*date", r"due\s*date"],
    "interest_rate": [r"rate\s+of\s+interest", r"interest\s*rate", r"\broi\b"],
}

# Any known label followed by a colon. On two-column layouts a row reads "Bank: X  Branch Name: Y", so a value
# is cut where the next label starts. A colon is required, so values like "Pune Camp Branch" are never cut.
_OTHER_LABELS = [r"customer\s*id", r"account\s*no", r"period", r"maturity\s*value", r"mode", r"nominee", r"purpose"]
NEXT_LABEL = re.compile(
    r"\s(?:" + "|".join([p for ps in LABEL_PATTERNS.values() for p in ps] + _OTHER_LABELS) + r")\s*[:]",
    re.IGNORECASE)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


@dataclass
class Row:
    text: str
    confidences: list[float] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return self.confidence_from(0)

    def confidence_from(self, char_pos: int) -> float:
        """Mean confidence of the words starting at or after char_pos (i.e. the value, not the label)."""
        good, pos = [], 0
        for word, conf in zip(self.text.split(" "), self.confidences):
            if pos + len(word) > char_pos and conf >= 0:
                good.append(conf)
            pos += len(word) + 1
        if not good:
            good = [c for c in self.confidences if c >= 0]
        return sum(good) / len(good) if good else 0.0


@dataclass
class ExtractedValue:
    field_name: str
    value: str | None
    confidence: float | None
    needs_review: bool
    note: str = ""


@dataclass
class OCRResult:
    status: str  # completed | failed | unavailable
    engine: str
    message: str
    text: str = ""
    mean_confidence: float | None = None
    duration_ms: int = 0
    fields: list[ExtractedValue] = field(default_factory=list)


# ---------------- engine setup ----------------

def find_tesseract() -> str | None:
    candidates = [settings.tesseract_cmd] if settings.tesseract_cmd else []
    candidates += [shutil.which("tesseract") or "",
                   r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                   r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def engine_status() -> dict:
    cmd = find_tesseract()
    if not cmd:
        return {"available": False, "engine": "tesseract", "version": None,
                "message": "Tesseract not found. Install it or set TESSERACT_CMD."}
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        version = str(pytesseract.get_tesseract_version())
    except Exception as exc:  # pragma: no cover - environment specific
        return {"available": False, "engine": "tesseract", "version": None, "message": f"Tesseract failed: {exc}"}
    return {"available": True, "engine": "tesseract", "version": version, "message": "OCR engine ready"}


# ---------------- image loading ----------------

def load_pages(data: bytes, content_type: str, max_pages: int = 3) -> list[Image.Image]:
    if content_type == "application/pdf":
        import fitz  # PyMuPDF
        pages = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in list(doc)[:max_pages]:
                pix = page.get_pixmap(dpi=300)
                pages.append(Image.open(io.BytesIO(pix.tobytes("png"))))
        return pages
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return [img]


def preprocess(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    if img.width < 1600:  # small photos/scans read much better when upscaled
        scale = 1600 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    return ImageOps.autocontrast(img)


def image_to_rows(img: Image.Image) -> list[Row]:
    """Run Tesseract and group words into visual rows (so 'Label  value' columns join up)."""
    import pytesseract
    d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, timeout=90)
    words = []
    for i, txt in enumerate(d["text"]):
        txt = (txt or "").strip()
        if not txt:
            continue
        words.append((d["top"][i], d["height"][i], d["left"][i], txt, float(d["conf"][i])))
    words.sort(key=lambda w: (w[0], w[2]))

    rows: list[list[tuple]] = []
    for w in words:
        center = w[0] + w[1] / 2
        placed = False
        for row in rows:
            top = min(x[0] for x in row)
            bottom = max(x[0] + x[1] for x in row)
            if top <= center <= bottom:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])
    result = []
    for row in rows:
        row.sort(key=lambda x: x[2])
        result.append(Row(" ".join(x[3] for x in row), [x[4] for x in row]))
    return result


# ---------------- value parsing ----------------

def parse_amount(s: str) -> float | None:
    s = s.replace("₹", " ").replace("INR", " ").replace("Rs.", " ").replace("Rs", " ")
    m = re.search(r"(\d{1,3}(?:,\d{2,3})+|\d{4,})(?:\.(\d{1,2}))?", s)
    if not m:
        return None
    whole = m.group(1).replace(",", "")
    frac = m.group(2) or "0"
    try:
        return float(f"{whole}.{frac}")
    except ValueError:
        return None


def parse_date(s: str) -> date | None:
    s = s.strip()
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})[\s\-]+([A-Za-z]{3,9})[\s\-,]+(\d{4})", s)
    if m and m.group(2)[:3].lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1)))
        except ValueError:
            return None
    return None


def parse_rate(s: str) -> float | None:
    m = re.search(r"(\d{1,2}(?:\.\d{1,2})?)\s*%", s)
    if not m:
        m = re.search(r"\b(\d{1,2}\.\d{1,2})\b", s)
    if not m:
        return None
    v = float(m.group(1))
    return v if 0 < v < 30 else None


def parse_fdr_number(s: str) -> str | None:
    m = re.search(r"[A-Z0-9][A-Z0-9/\-]{4,}", s.upper())
    return m.group(0).strip("-/") if m else None


def clean_text_value(s: str) -> str | None:
    s = s.strip(" :-–|.,")
    return s[:200] if len(s) >= 2 else None


PARSERS = {
    "principal_amount": lambda s: (lambda v: f"{v:.2f}" if v is not None else None)(parse_amount(s)),
    "issue_date": lambda s: (lambda v: v.isoformat() if v else None)(parse_date(s)),
    "maturity_date": lambda s: (lambda v: v.isoformat() if v else None)(parse_date(s)),
    "interest_rate": lambda s: (lambda v: f"{v:.2f}" if v is not None else None)(parse_rate(s)),
    "fdr_number": parse_fdr_number,
}


def extract_fields(rows: list[Row], low_conf: float = 70.0) -> list[ExtractedValue]:
    results: dict[str, ExtractedValue] = {}
    used_rows: dict[str, int] = {}
    for fname in FIELD_NAMES:
        found = None
        for pattern in LABEL_PATTERNS[fname]:
            rx = re.compile(pattern + r"\s*[:\-–.]?\s*", re.IGNORECASE)
            for idx, row in enumerate(rows):
                if fname == "principal_amount" and re.search(r"maturity", row.text, re.IGNORECASE):
                    continue
                if fname == "institution_name" and re.search(r"bank|branch", row.text, re.IGNORECASE):
                    continue
                m = rx.search(row.text)
                if not m:
                    continue
                raw = row.text[m.end():].strip()
                conf = row.confidence_from(m.end())
                if not raw and idx + 1 < len(rows):  # value printed on the next line
                    raw, conf = rows[idx + 1].text.strip(), rows[idx + 1].confidence
                if not raw:
                    continue
                cut = NEXT_LABEL.search(" " + raw)
                if cut and cut.start() > 0:
                    raw = raw[:cut.start() - 1].strip()  # -1: offset of the leading space added above
                found = (idx, raw, conf)
                break
            if found:
                break

        if not found and fname == "bank_name":  # fall back to a letterhead line containing "BANK"
            for idx, row in enumerate(rows[:6]):
                if re.search(r"\bbank\b", row.text, re.IGNORECASE):
                    found = (idx, row.text, row.confidence * 0.8)
                    break

        if not found:
            results[fname] = ExtractedValue(fname, None, None, True, "Not found on the document - enter manually.")
            continue

        idx, raw, conf = found
        parser = PARSERS.get(fname, clean_text_value)
        value = parser(raw)
        if value is None:
            results[fname] = ExtractedValue(fname, raw[:200], round(conf * 0.5, 1), True,
                                            "Text found but could not be read reliably - please check.")
        else:
            needs = conf < low_conf
            results[fname] = ExtractedValue(fname, value, round(conf, 1), needs,
                                            "Low OCR confidence - please verify." if needs else "")
        used_rows[fname] = idx
    return [results[f] for f in FIELD_NAMES]


# ---------------- entry point ----------------

def run_ocr(data: bytes, content_type: str, low_conf: float = 70.0) -> OCRResult:
    start = time.perf_counter()
    status = engine_status()
    if not status["available"]:
        return OCRResult("unavailable", "tesseract", status["message"],
                         fields=[ExtractedValue(f, None, None, True, "OCR unavailable - enter manually.") for f in FIELD_NAMES])
    try:
        rows: list[Row] = []
        for page in load_pages(data, content_type):
            rows.extend(image_to_rows(preprocess(page)))
    except Exception as exc:
        return OCRResult("failed", f"tesseract {status['version']}", f"OCR could not process this file ({type(exc).__name__}).",
                         duration_ms=int((time.perf_counter() - start) * 1000),
                         fields=[ExtractedValue(f, None, None, True, "OCR failed - enter manually.") for f in FIELD_NAMES])

    all_conf = [c for r in rows for c in r.confidences if c >= 0]
    fields = extract_fields(rows, low_conf)
    found = sum(1 for f in fields if f.value)
    return OCRResult(
        status="completed",
        engine=f"tesseract {status['version']}",
        message=f"Read {len(rows)} text lines; recognised {found} of {len(FIELD_NAMES)} fields.",
        text="\n".join(r.text for r in rows),
        mean_confidence=round(sum(all_conf) / len(all_conf), 1) if all_conf else None,
        duration_ms=int((time.perf_counter() - start) * 1000),
        fields=fields,
    )


def to_python(field_name: str, value: str | None):
    """Convert a stored string value to the type used on FDRRecord."""
    if value in (None, ""):
        return None
    if field_name in ("principal_amount", "interest_rate"):
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None
    if field_name in ("issue_date", "maturity_date"):
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None
    return value
