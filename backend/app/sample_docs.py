"""Generates FICTIONAL sample documents (FDR receipts, payment proofs, a simulated bank letter).

These are synthetic and clearly marked as specimens; they are not valid financial instruments.
The layout uses printed "Label: value" rows so the OCR engine can read them.
"""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def inr_text(v: float) -> str:
    s = f"{int(round(v))}"
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"Rs. {s}.00"


def _frame(c: canvas.Canvas, bank: str, title: str):
    w, h = A4
    c.setStrokeColor(colors.HexColor("#0b2a5b"))
    c.setLineWidth(2)
    c.rect(15 * mm, 15 * mm, w - 30 * mm, h - 30 * mm)
    c.setFillColor(colors.HexColor("#0b2a5b"))
    c.rect(15 * mm, h - 45 * mm, w - 30 * mm, 30 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(w / 2, h - 28 * mm, bank.upper())
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, h - 36 * mm, "FICTIONAL BANK - SYNTHETIC SPECIMEN FOR SURAKSHAFD HACKATHON DEMO")
    c.setFillColor(colors.HexColor("#0b2a5b"))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, h - 60 * mm, title)


def _rows(c: canvas.Canvas, rows: list[tuple[str, str]], top_mm: float = 75):
    w, h = A4
    y = h - top_mm * mm
    for label, value in rows:
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(28 * mm, y, f"{label}:")
        c.setFont("Helvetica", 13)
        c.drawString(85 * mm, y, value)
        c.setStrokeColor(colors.HexColor("#cfd8e3"))
        c.setLineWidth(0.5)
        c.line(28 * mm, y - 3 * mm, w - 28 * mm, y - 3 * mm)
        y -= 11 * mm
    return y


def _footer(c: canvas.Canvas, text: str):
    w, _ = A4
    c.setFillColor(colors.HexColor("#8a1c1c"))
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(w / 2, 22 * mm, text)


def fdr_receipt_pdf(*, bank: str, branch: str, fdr_number: str, institution: str, holder: str, account_masked: str,
                    principal: float, rate: float, issue: date, maturity: date) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Fictional FDR {fdr_number}")
    _frame(c, bank, "FIXED DEPOSIT RECEIPT")
    tenure_days = (maturity - issue).days
    maturity_amt = principal * (1 + rate / 100 * tenure_days / 365)
    y = _rows(c, [
        ("Bank Name", bank),
        ("Branch", branch),
        ("FDR No.", fdr_number),
        ("Institution Name", institution),
        ("Account Holder", holder),
        ("Account No.", account_masked),
        ("Principal Amount", inr_text(principal)),
        ("Rate of Interest", f"{rate:.2f}% p.a."),
        ("Date of Issue", issue.strftime("%d/%m/%Y")),
        ("Date of Maturity", maturity.strftime("%d/%m/%Y")),
        ("Maturity Value", inr_text(maturity_amt)),
        ("Purpose", "Security Deposit (AICTE demo)"),
    ])
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawString(28 * mm, y - 6 * mm, "Lien marked in favour of the approving authority (fictional demonstration text).")
    c.drawString(28 * mm, y - 30 * mm, "Authorised Signatory (specimen)")
    c.line(28 * mm, y - 24 * mm, 80 * mm, y - 24 * mm)
    _footer(c, "SPECIMEN ONLY - synthetic data generated for a hackathon demonstration. Not a valid financial instrument.")
    c.showPage()
    c.save()
    return buf.getvalue()


def payment_proof_pdf(*, bank: str, institution: str, fdr_number: str, principal: float, paid_on: date, txn: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Fictional payment proof {txn}")
    _frame(c, bank, "PAYMENT ADVICE (SPECIMEN)")
    _rows(c, [
        ("Remitter", institution),
        ("Purpose", f"Funding of FDR {fdr_number}"),
        ("Amount", inr_text(principal)),
        ("Transaction Ref", txn),
        ("Date", paid_on.strftime("%d/%m/%Y")),
        ("Mode", "NEFT (fictional)"),
    ])
    _footer(c, "SPECIMEN ONLY - synthetic payment advice for a hackathon demonstration.")
    c.showPage()
    c.save()
    return buf.getvalue()


def simulated_bank_letter_pdf(*, bank: str, fdr_number: str, institution: str, principal: float, on: date) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Simulated bank confirmation")
    _frame(c, bank, "DEMO / SIMULATED BANK CONFIRMATION")
    y = _rows(c, [
        ("FDR No.", fdr_number),
        ("In favour of", institution),
        ("Principal Amount", inr_text(principal)),
        ("Letter Date", on.strftime("%d/%m/%Y")),
        ("Status", "Confirmed (SIMULATED)"),
    ])
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#8a1c1c"))
    c.drawString(28 * mm, y - 8 * mm, "This letter is SIMULATED. No real bank issued or confirmed it.")
    _footer(c, "Genuine verification requires confirmation obtained independently from the issuing bank.")
    c.showPage()
    c.save()
    return buf.getvalue()


def pdf_to_scanned_png(pdf_bytes: bytes) -> bytes:
    """Render a PDF page as a slightly rotated grey 'scan', to show OCR working on images too."""
    import fitz
    from PIL import Image, ImageFilter

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        pix = doc[0].get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    img = img.rotate(0.8, expand=True, fillcolor=255).filter(ImageFilter.GaussianBlur(0.6))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def term_deposit_advice_pdf(*, bank: str, branch: str, receipt_no: str, institution: str, principal: float,
                            rate: float, issue: date, maturity: date, customer_id: str, account_masked: str,
                            amount_words: str) -> bytes:
    """A second, differently laid-out receipt (two-column label/value grid, 'dd-Mon-yyyy' dates)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Fictional term deposit advice {receipt_no}")
    w, h = A4
    green = colors.HexColor("#14532d")
    # letterhead
    c.setFillColor(green)
    c.rect(15 * mm, h - 40 * mm, w - 30 * mm, 25 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.circle(27 * mm, h - 27.5 * mm, 7 * mm, fill=1, stroke=0)
    c.setFillColor(green)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(27 * mm, h - 29.5 * mm, "GV")
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(38 * mm, h - 26 * mm, bank.upper())
    c.setFont("Helvetica", 9)
    c.drawString(38 * mm, h - 33 * mm, "Fictional bank for the SurakshaFD hackathon demonstration - not a real institution")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(15 * mm, h - 52 * mm, "TERM DEPOSIT ADVICE")
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 15 * mm, h - 52 * mm, f"Printed on {issue.strftime('%d-%b-%Y')}  |  Original copy")
    c.setStrokeColor(green)
    c.setLineWidth(1)
    c.line(15 * mm, h - 55 * mm, w - 15 * mm, h - 55 * mm)

    maturity_value = principal * (1 + rate / 100 * (maturity - issue).days / 365)
    rows = [
        (("Name of Bank", bank), ("Branch Name", branch)),
        (("Receipt No.", receipt_no), ("Customer ID", customer_id)),
        (("Depositor Name", institution), None),
        (("Institution", institution), None),
        (("Deposit Amount", inr_text(principal)), ("Rate of Interest", f"{rate:.2f}% p.a.")),
        (("Date of Deposit", issue.strftime("%d-%b-%Y")), ("Maturity Date", maturity.strftime("%d-%b-%Y"))),
        (("Period", f"{(maturity - issue).days} days"), ("Maturity Value", inr_text(maturity_value))),
        (("Account No.", account_masked), ("Mode", "Single - Institutional")),
    ]
    y = h - 66 * mm
    col_x = [15 * mm, 108 * mm]
    for left, right in rows:
        cells = [left] + ([right] if right else [])
        for i, (label, value) in enumerate(cells):
            x = col_x[i]
            width = (w - 30 * mm) if right is None else 90 * mm
            c.setStrokeColor(colors.HexColor("#c8d5cc"))
            c.setFillColor(colors.HexColor("#f4f8f5"))
            c.rect(x, y - 3.5 * mm, width - 3 * mm, 10 * mm, fill=1, stroke=1)
            c.setFillColor(colors.HexColor("#374151"))
            c.setFont("Helvetica-Bold", 11)
            c.drawString(x + 2.5 * mm, y, f"{label}:")
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 11)
            c.drawString(x + 2.5 * mm + c.stringWidth(f"{label}: ", "Helvetica-Bold", 11) + 1 * mm, y, value)
        y -= 13 * mm
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(15 * mm, y, f"Amount in words: {amount_words}")
    y -= 12 * mm
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#4b5563"))
    for line in ["Terms: premature withdrawal subject to bank rules (fictional). Deposit is marked under lien to the",
                 "approving authority as security deposit (demonstration text only). Interest compounded quarterly."]:
        c.drawString(15 * mm, y, line)
        y -= 5 * mm
    c.setStrokeColor(colors.black)
    c.line(w - 75 * mm, y - 12 * mm, w - 20 * mm, y - 12 * mm)
    c.setFont("Helvetica", 9)
    c.drawString(w - 75 * mm, y - 17 * mm, "Branch Manager (specimen signature)")
    _footer(c, "SPECIMEN ONLY - synthetic term deposit advice for a hackathon demonstration. Not a valid instrument.")
    c.showPage()
    c.save()
    return buf.getvalue()


def _perspective_coeffs(dst, src):
    """Coefficients for PIL's PERSPECTIVE transform mapping output points (dst) to input points (src)."""
    a = []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
    n = 8  # Gaussian elimination on the 8x9 augmented matrix
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(a[r][i]))
        a[i], a[p] = a[p], a[i]
        for r in range(n):
            if r != i:
                f = a[r][i] / a[i][i]
                a[r] = [rv - f * iv for rv, iv in zip(a[r], a[i])]
    return [a[i][8] / a[i][i] for i in range(n)]


def pdf_to_phone_photo_jpg(pdf_bytes: bytes) -> bytes:
    """Simulates a phone photo of a printed receipt: slight tilt, uneven light, sensor noise, JPEG compression."""
    import random

    import fitz
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    rnd = random.Random(7)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        pix = doc[0].get_pixmap(dpi=170)
    page = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    W, H = page.size
    bg = Image.new("RGB", (int(W * 1.12), int(H * 1.08)), (92, 84, 74))  # desk
    ox, oy = int(W * 0.06), int(H * 0.04)
    bg.paste(page, (ox, oy))
    BW, BH = bg.size
    # mild keystone, as if the phone was held slightly off-axis
    dst = [(0, 0), (BW, 0), (BW, BH), (0, BH)]
    src = [(BW * 0.012, BH * 0.008), (BW * 0.985, -BH * 0.004), (BW * 1.0, BH * 0.995), (-BW * 0.006, BH * 1.004)]
    img = bg.transform(bg.size, Image.PERSPECTIVE, _perspective_coeffs(dst, src), Image.BICUBIC, fillcolor=(92, 84, 74))
    img = img.rotate(-1.2, resample=Image.BICUBIC, fillcolor=(92, 84, 74))
    # uneven lighting: darker towards the bottom-right corner
    shade = Image.new("L", img.size, 255)
    d = ImageDraw.Draw(shade)
    for i in range(0, 256, 4):
        d.rectangle([img.width * i / 512, img.height * i / 512, img.width, img.height], fill=255 - i // 6)
    img = ImageChops.multiply(img, Image.merge("RGB", [shade] * 3))
    noise = Image.effect_noise(img.size, 14).convert("RGB")
    img = Image.blend(img, ImageChops.multiply(img, noise.point(lambda p: 200 + p // 5)), 0.35)
    img = img.filter(ImageFilter.GaussianBlur(0.7)).resize((int(img.width * 0.85), int(img.height * 0.85)))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=80)
    return out.getvalue()
