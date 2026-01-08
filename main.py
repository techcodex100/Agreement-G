# main.py
from __future__ import annotations

from fastapi import FastAPI, Response
from pydantic import BaseModel, EmailStr
from typing import List
from io import BytesIO
from decimal import Decimal
from datetime import date, datetime

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
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


app = FastAPI()


# -----------------------------
# Helpers
# -----------------------------
def safe_str(s: str | None) -> str:
    return (s or "").strip()


def normalize_website(w: str) -> str:
    """
    Keep it human friendly in PDF. If you later want strict URL validation,
    enforce https:// in your frontend.
    """
    w = safe_str(w)
    if not w:
        return ""
    # Avoid double "Website:" looking weird
    return w.replace("http://", "").replace("https://", "").rstrip("/")


def parse_date_loose(d: str) -> str:
    """
    Your input example uses '02.02.2022'. We'll try a few common patterns and
    output a consistent 'DD MMM YYYY'. If parsing fails, return the raw string.
    """
    raw = safe_str(d)
    if not raw:
        return ""
    patterns = ["%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]
    for p in patterns:
        try:
            dt = datetime.strptime(raw, p).date()
            return dt.strftime("%d %b %Y")
        except Exception:
            pass
    return raw


def money_like(s: str) -> str:
    """
    Light formatting for amount-like fields. Keeps strings if not numeric.
    """
    raw = safe_str(s)
    if not raw:
        return ""
    try:
        # Allow commas in input
        x = Decimal(raw.replace(",", ""))
        # No currency symbol assumption
        return f"{x:,.2f}"
    except Exception:
        return raw


# -----------------------------
# Request Model
# -----------------------------
class AgreementData(BaseModel):
    contract_no: str
    date: str  # we'll format for display
    website: str
    company_name: str
    email: EmailStr
    address: str
    city: str
    state: str
    gst_number: str

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
    documents: str
    payment_terms: str


# -----------------------------
# PDF Builder
# -----------------------------
def build_agreement_pdf(data: AgreementData) -> bytes:
    buffer = BytesIO()

    # If you want custom fonts, uncomment and place .ttf files.
    # pdfmetrics.registerFont(TTFont("Inter", "Inter-Regular.ttf"))
    # pdfmetrics.registerFont(TTFont("Inter-Bold", "Inter-Bold.ttf"))

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Sales Contract - {safe_str(data.contract_no)}",
        author=safe_str(data.company_name),
    )

    styles = getSampleStyleSheet()

    # Base styles
    Title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        alignment=1,  # center
        spaceAfter=6,
        textColor=colors.HexColor("#0f172a"),  # slate-900
    )

    SubTitle = ParagraphStyle(
        "SubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#475569"),  # slate-600
        spaceAfter=10,
    )

    H2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6,
    )

    Body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
    )

    Muted = ParagraphStyle(
        "Muted",
        parent=Body,
        textColor=colors.HexColor("#475569"),
    )

    Small = ParagraphStyle(
        "Small",
        parent=Body,
        fontSize=9,
        leading=12,
    )

    # Header/footer for all pages
    def on_page(canvas, _doc):
        w, h = A4

        # top rule
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))  # slate-200
        canvas.setLineWidth(0.7)
        canvas.line(doc.leftMargin, h - doc.topMargin + 6, w - doc.rightMargin, h - doc.topMargin + 6)

        # footer
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#64748b"))  # slate-500
        page_num = canvas.getPageNumber()
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 10, f"Sales Contract • Contract No: {safe_str(data.contract_no)}")
        canvas.drawRightString(w - doc.rightMargin, doc.bottomMargin - 10, f"Page {page_num}")
        canvas.restoreState()

    story = []

    # --- Company Block ---
    story.append(Paragraph(safe_str(data.company_name).upper(), Title))

    website = normalize_website(data.website)
    contact_line_parts = []
    if safe_str(data.address):
        contact_line_parts.append(safe_str(data.address))
    loc = ", ".join([p for p in [safe_str(data.city), safe_str(data.state)] if p])
    if loc:
        contact_line_parts.append(loc)
    if safe_str(data.gst_number):
        contact_line_parts.append(f"GST: {safe_str(data.gst_number)}")
    if website:
        contact_line_parts.append(f"Website: {website}")
    contact_line_parts.append(f"Email: {safe_str(data.email)}")

    story.append(Paragraph(" • ".join(contact_line_parts), SubTitle))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceBefore=6, spaceAfter=10))

    # --- Contract Info Row ---
    contract_info = [
        [Paragraph("<b>Document</b>", Small), Paragraph("<b>Contract No</b>", Small), Paragraph("<b>Date</b>", Small)],
        [
            Paragraph("Sales Contract", Body),
            Paragraph(safe_str(data.contract_no), Body),
            Paragraph(parse_date_loose(data.date), Body),
        ],
    ]
    t = Table(contract_info, colWidths=[60 * mm, 60 * mm, 50 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),  # slate-100
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 10))

    # --- Parties (3 columns) ---
    def block_lines(title: str, lines: List[str]) -> Paragraph:
        safe_lines = [safe_str(x) for x in (lines or []) if safe_str(x)]
        if not safe_lines:
            safe_lines = ["—"]
        html = f"<b>{title}</b><br/>" + "<br/>".join(safe_lines)
        return Paragraph(html, Body)

    parties = Table(
        [
            [
                block_lines("SELLER", data.seller),
                block_lines("CONSIGNEE", data.consignee),
                block_lines("NOTIFY PARTY", data.notify_party),
            ]
        ],
        colWidths=[doc.width / 3, doc.width / 3, doc.width / 3],
    )
    parties.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(parties)
    story.append(Spacer(1, 12))

    # --- Product Table ---
    story.append(Paragraph("PRODUCT DETAILS", H2))

    product_table = Table(
        [
            [
                Paragraph("<b>Product</b>", Small),
                Paragraph("<b>Quantity</b>", Small),
                Paragraph("<b>Price</b>", Small),
                Paragraph("<b>Amount</b>", Small),
            ],
            [
                Paragraph(safe_str(data.product) or "—", Body),
                Paragraph(safe_str(data.quantity) or "—", Body),
                Paragraph(safe_str(data.price) or "—", Body),
                Paragraph(money_like(data.amount) or "—", Body),
            ],
        ],
        colWidths=[doc.width * 0.40, doc.width * 0.20, doc.width * 0.20, doc.width * 0.20],
    )

    product_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),  # blue-100
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(product_table)
    story.append(Spacer(1, 12))

    # --- Other Details (2-column key/value table) ---
    story.append(Paragraph("SHIPMENT & PAYMENT DETAILS", H2))

    detail_rows = [
        ("Packing", data.packing),
        ("Loading Port", data.loading_port),
        ("Destination Port", data.destination_port),
        ("Shipment", data.shipment),
        ("Seller’s Bank", data.sellers_bank),
        ("Account No.", data.account_no),
        ("Documents", data.documents),
        ("Payment Terms", data.payment_terms),
    ]

    detail_table_data = []
    for k, v in detail_rows:
        detail_table_data.append(
            [
                Paragraph(f"<b>{safe_str(k)}</b>", Small),
                Paragraph(safe_str(v) or "—", Body),
            ]
        )

    details_table = Table(detail_table_data, colWidths=[doc.width * 0.28, doc.width * 0.72])
    details_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),  # slate-50 for keys
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(details_table)
    story.append(Spacer(1, 12))

    # --- Arbitration ---
    story.append(Paragraph("LEGAL", H2))

    appointed_by = safe_str(data.company_name)  # you asked: company_name or seller
    if data.seller and safe_str(data.seller[0]):
        # If you'd rather appoint by seller, keep this. If not, remove this block.
        appointed_by = safe_str(data.seller[0])

    place = ", ".join([p for p in [safe_str(data.city), safe_str(data.state)] if p]) or safe_str(data.address) or "—"

    arbitration_text = (
        "<b>Arbitration</b><br/>"
        "In the event of any dispute between the parties arising out of this contract, "
        f"all disputes shall be settled by arbitration through a sole arbitrator appointed by <b>{appointed_by}</b>. "
        f"The place of arbitration shall be <b>{place}</b>, and the laws of India shall apply."
    )
    story.append(Paragraph(arbitration_text, Body))
    story.append(Spacer(1, 8))

    terms_text = (
        "<b>Terms & Conditions</b><br/>"
        "1) In case of port congestion / skippance of vessel or any other port disturbances, "
        "the supplier or exporter will not be liable for any claim.<br/>"
        "2) Quality approved at load port by independent surveyors is final and shall be acceptable by both parties. "
        "The seller will not be liable for any claim at destination port."
    )
    story.append(Paragraph(terms_text, Body))
    story.append(Spacer(1, 14))

    # --- Signatures ---
    story.append(Paragraph("ACCEPTANCE & SIGNATURES", H2))
    story.append(Paragraph("Accepted by the parties to this Sales Contract:", Muted))
    story.append(Spacer(1, 10))

    sign_table = Table(
        [
            [Paragraph("<b>For Seller</b>", Body), Paragraph("<b>For Consignee</b>", Body), Paragraph("<b>For Notify Party</b>", Body)],
            [Spacer(1, 22), Spacer(1, 22), Spacer(1, 22)],
            [Paragraph("Name / Signature:", Small), Paragraph("Name / Signature:", Small), Paragraph("Name / Signature:", Small)],
            [Paragraph("Date:", Small), Paragraph("Date:", Small), Paragraph("Date:", Small)],
        ],
        colWidths=[doc.width / 3, doc.width / 3, doc.width / 3],
    )
    sign_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 1), (0, 1), 0.8, colors.HexColor("#94a3b8")),
                ("LINEBELOW", (1, 1), (1, 1), 0.8, colors.HexColor("#94a3b8")),
                ("LINEBELOW", (2, 1), (2, 1), 0.8, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(sign_table)

    # Build PDF
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    buffer.seek(0)
    return buffer.read()


# -----------------------------
# API Endpoint
# -----------------------------
@app.post("/generate-agreement/")
async def generate_agreement(data: AgreementData):
    pdf_bytes = build_agreement_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Agreement.pdf"},
    )
