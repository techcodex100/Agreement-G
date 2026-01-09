from __future__ import annotations

from fastapi import FastAPI, Response
from pydantic import BaseModel, EmailStr
from typing import List
from io import BytesIO
from decimal import Decimal
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

app = FastAPI()


# -----------------------------
# Helpers
# -----------------------------
def s(x) -> str:
    return (x or "").strip()


def normalize_website(w: str) -> str:
    w = s(w)
    if not w:
        return ""
    return w.replace("http://", "").replace("https://", "").rstrip("/")


def parse_date_loose(d: str) -> str:
    raw = s(d)
    if not raw:
        return ""
    patterns = ["%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"]
    for p in patterns:
        try:
            dt = datetime.strptime(raw, p).date()
            return dt.strftime("%d %b %Y")
        except Exception:
            pass
    return raw


def money_like(x: str) -> str:
    raw = s(x)
    if not raw:
        return ""
    try:
        val = Decimal(raw.replace(",", ""))
        return f"{val:,.2f}"
    except Exception:
        return raw


def p(txt: str, style: ParagraphStyle) -> Paragraph:
    # We use minimal controlled markup (<b>, <br/>) only.
    return Paragraph(txt, style)


def split_documents_to_grid(doc_text: str, cols: int = 3) -> List[List[str]]:
    """
    Turn the documents block into a compact multi-column grid.
    Input can be:
      "1) Invoice\n2) PL\n3) BL"
    Output: table rows like [col1, col2, col3]
    """
    raw_lines = [s(x) for x in (doc_text or "").splitlines() if s(x)]
    if not raw_lines:
        raw_lines = ["—"]

    # Clean "1) " prefix for nicer look
    cleaned = []
    for line in raw_lines:
        # remove leading "1) " or "1." etc (best-effort)
        cleaned.append(line.lstrip("0123456789). ").strip() or line)

    # Build row-wise grid
    rows = []
    r = 0
    while r < len(cleaned):
        row = cleaned[r:r + cols]
        while len(row) < cols:
            row.append("")
        rows.append(row)
        r += cols
    return rows


# -----------------------------
# Request Model (matches your payload)
# -----------------------------
class AgreementData(BaseModel):
    contract_no: str
    date: str

    website: str
    company_name: str
    email: EmailStr
    address: str

    gst_number: str = ""
    iec_number: str = ""

    seller: List[str]
    consignee: List[str]
    notify_party: List[str]

    product: str
    quantity: str
    price: str
    amount: str

    packing: str
    loading_port: str
    destination_port: str
    shipment: str

    sellers_bank: str
    account_no: str
    bank_ifsc: str = ""
    bank_swift: str = ""

    documents: str
    payment_terms: str


# -----------------------------
# PDF Builder (single-page optimized)
# -----------------------------
def build_agreement_pdf(data: AgreementData) -> bytes:
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Sales Contract - {s(data.contract_no)}",
        author=s(data.company_name),
    )

    styles = getSampleStyleSheet()

    Title = ParagraphStyle(
        "Title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13.2,
        leading=15.5,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    )

    Small = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )

    Body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )

    H2 = ParagraphStyle(
        "H2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.6,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=4,
        spaceAfter=3,
    )

    # ---------- Header (compact) ----------
    story = []
    story.append(p(s(data.company_name).upper(), Title))

    website = normalize_website(data.website) or "—"
    email = s(str(data.email)) or "—"
    address = s(data.address) or "—"
    iec = s(data.iec_number) or "—"
    gst = s(data.gst_number) or "—"

    header_left = f"<b>Website:</b> {website}<br/><b>Email:</b> {email}<br/><b>Address:</b> {address}"
    header_right = f"<b>IEC:</b> {iec}<br/><b>GST:</b> {gst}"

    header_tbl = Table(
        [[p(header_left, Small), p(header_right, Small)]],
        colWidths=[doc.width * 0.72, doc.width * 0.28],
    )
    header_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(header_tbl)

    # ---------- Contract meta (tight) ----------
    meta = Table(
        [
            [p("<b>Sales Contract</b>", Small),
             p(f"<b>Contract No:</b> {s(data.contract_no) or '—'}", Small),
             p(f"<b>Date:</b> {parse_date_loose(data.date) or '—'}", Small)]
        ],
        colWidths=[doc.width * 0.28, doc.width * 0.42, doc.width * 0.30],
    )
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 4))

    # ---------- Parties (tight table) ----------
    def party_block(title: str, lines: List[str]) -> Paragraph:
        lines_clean = [s(x) for x in (lines or []) if s(x)]
        if not lines_clean:
            lines_clean = ["—"]
        return p(f"<b>{title}</b><br/>{'<br/>'.join(lines_clean)}", Body)

    parties = Table(
        [[party_block("SELLER", data.seller),
          party_block("CONSIGNEE", data.consignee),
          party_block("NOTIFY PARTY", data.notify_party)]],
        colWidths=[doc.width / 3, doc.width / 3, doc.width / 3],
    )
    parties.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(parties)
    story.append(Spacer(1, 4))

    # ---------- Product (compact) ----------
    story.append(p("PRODUCT DETAILS", H2))
    product_table = Table(
        [
            [p("<b>Product</b>", Small), p("<b>Quantity</b>", Small), p("<b>Price</b>", Small), p("<b>Amount</b>", Small)],
            [
                p(s(data.product) or "—", Body),
                p(s(data.quantity) or "—", Body),
                p(s(data.price) or "—", Body),
                p(money_like(data.amount) or "—", Body),
            ],
        ],
        colWidths=[doc.width * 0.44, doc.width * 0.18, doc.width * 0.19, doc.width * 0.19],
    )
    product_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(product_table)
    story.append(Spacer(1, 4))

    # ---------- Shipment (tight key/value table, fewer rows) ----------
    story.append(p("SHIPMENT DETAILS", H2))
    ship_rows = [
        ("Packing", s(data.packing) or "—"),
        ("Loading Port", s(data.loading_port) or "—"),
        ("Destination Port", s(data.destination_port) or "—"),
        ("Shipment", s(data.shipment) or "—"),
    ]
    ship_tbl = Table(
        [[p(f"<b>{k}</b>", Small), p(v, Body)] for k, v in ship_rows],
        colWidths=[doc.width * 0.26, doc.width * 0.74],
    )
    ship_tbl.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(ship_tbl)
    story.append(Spacer(1, 3))

    # ---------- Bank details as ONE paragraph (your request) ----------
    story.append(p("BANK DETAILS (SELLER)", H2))
    bank_line = (
        f"<b>Bank:</b> {s(data.sellers_bank) or '—'}  |  "
        f"<b>A/c:</b> {s(data.account_no) or '—'}  |  "
        f"<b>IFSC:</b> {s(data.bank_ifsc) or '—'}  |  "
        f"<b>SWIFT:</b> {s(data.bank_swift) or '—'}"
    )
    story.append(p(bank_line, Body))
    story.append(Spacer(1, 4))

    # ---------- Documents: multi-column grid inside a bordered block ----------
    story.append(p("REQUIRED DOCUMENTS", H2))
    doc_grid = split_documents_to_grid(data.documents, cols=3)
    doc_tbl = Table(
        [[p(s(cell), Body) for cell in row] for row in doc_grid],
        colWidths=[doc.width / 3, doc.width / 3, doc.width / 3],
    )
    doc_tbl.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    wrapper = Table([[doc_tbl]], colWidths=[doc.width])
    wrapper.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(wrapper)
    story.append(Spacer(1, 4))

    # ---------- Payment terms (compact) ----------
    story.append(p("PAYMENT TERMS", H2))
    pay = "<br/>".join([s(line) for line in (data.payment_terms or "").splitlines() if s(line)]) or "—"
    story.append(p(pay, Body))
    story.append(Spacer(1, 4))

    # ---------- Legal (condensed to prevent page 2) ----------
    story.append(p("LEGAL", H2))
    appointed_by = s(data.seller[0]) if data.seller and s(data.seller[0]) else s(data.company_name)
    place = s(data.address) or "—"

    arbitration = (
        f"<b>Arbitration:</b> Disputes shall be settled by a sole arbitrator appointed by <b>{appointed_by}</b>. "
        f"Place of arbitration: <b>{place}</b>. Laws of India shall apply."
    )
    story.append(p(arbitration, Body))

    terms = (
        "<b>Terms:</b> (1) Seller not liable for delays due to port congestion/skippance/disturbances. "
        "(2) Quality approved at load port by independent surveyors is final; no claims at destination."
    )
    story.append(p(terms, Body))
    story.append(Spacer(1, 5))

    # ---------- Signatures (tight) ----------
    sign_tbl = Table(
        [
            [p("<b>For Seller</b>", Body), p("<b>For Consignee</b>", Body), p("<b>For Notify Party</b>", Body)],
            [p("Name / Signature: ____________________", Small),
             p("Name / Signature: ____________________", Small),
             p("Name / Signature: ____________________", Small)],
            [p("Date: ____________", Small), p("Date: ____________", Small), p("Date: ____________", Small)],
        ],
        colWidths=[doc.width / 3, doc.width / 3, doc.width / 3],
    )
    sign_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    story.append(sign_tbl)

    # Build PDF (Platypus will still add a 2nd page if content is too long)
    doc.build(story)

    buf.seek(0)
    return buf.read()


@app.post("/generate-agreement/")
async def generate_agreement(data: AgreementData):
    pdf_bytes = build_agreement_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Agreement.pdf"},
    )
