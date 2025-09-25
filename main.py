from fastapi import FastAPI, Response
from pydantic import BaseModel
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = FastAPI()

class AgreementData(BaseModel):
    contract_no: str
    date: str
    website: str
    company_name: str
    email: str
    organization: str
    address: str
    gst_number: str
    seller: list[str]
    consignee: list[str]
    notify_party: list[str]   # ✅ only one notify party
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


@app.post("/generate-agreement/")
async def generate_agreement(data: AgreementData):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    left_margin, right_margin = 50, width - 50
    y = height - 40

    # 🔷 Header
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.grey)
    c.drawString(left_margin, y, f"Website: {data.website}")
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, y, data.company_name.upper())
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.grey)
    c.drawRightString(right_margin, y, f"Email: {data.email}")

    y -= 20
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, y, data.organization)

    # 🔷 Address + GST
    y -= 40
    para = Paragraph(f"<b>Address:</b> {data.address}", normal)
    w, h = para.wrap(width/2, 50)
    para.drawOn(c, left_margin, y - h)

    para = Paragraph(f"<b>GST:</b> {data.gst_number}", normal)
    w, h2 = para.wrap(width/3, 50)
    para.drawOn(c, right_margin - w, y - h)

    y -= max(h, h2) + 30

    # 🔷 Title + Contract Info
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, "SALES CONTRACT")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(left_margin, y, f"Contract No: {data.contract_no}")
    c.drawRightString(right_margin, y, f"Date: {data.date}")
    y -= 40

    # 🔷 Seller (Left), Consignee (Center), Notify Party (Right)
    seller_para = Paragraph(f"<b>SELLER</b><br/>{'<br/>'.join(data.seller)}", normal)
    consignee_para = Paragraph(f"<b>CONSIGNEE</b><br/>{'<br/>'.join(data.consignee)}", normal)
    notify_para = Paragraph(f"<b>NOTIFY PARTY</b><br/>{'<br/>'.join(data.notify_party)}", normal)

    usable_width = width - (left_margin * 2)

    # Seller Left
    w1, h1 = seller_para.wrap(usable_width/3, 200)
    seller_para.drawOn(c, left_margin, y - h1)

    # Consignee Center
    w2, h2 = consignee_para.wrap(usable_width/3, 200)
    consignee_x = left_margin + (usable_width - w2) / 2
    consignee_para.drawOn(c, consignee_x, y - h2)

    # Notify Party Right
    w3, h3 = notify_para.wrap(usable_width/3, 200)
    notify_para.drawOn(c, right_margin - w3, y - h3)

    y -= max(h1, h2, h3) + 40

    # 🔷 Product Table (manual look)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.lightblue)
    c.rect(left_margin, y - 20, width - 100, 20, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.drawString(left_margin + 5, y - 15, "Product")
    c.drawString(left_margin + 160, y - 15, "Quantity")
    c.drawString(left_margin + 260, y - 15, "Price (CIF)")
    c.drawString(left_margin + 400, y - 15, "Amount (CIF)")

    y -= 20
    c.setFont("Helvetica", 9)
    c.rect(left_margin, y - 20, width - 100, 20, stroke=1, fill=0)
    c.drawString(left_margin + 5, y - 15, data.product)
    c.drawString(left_margin + 160, y - 15, data.quantity)
    c.drawString(left_margin + 260, y - 15, data.price)
    c.drawString(left_margin + 400, y - 15, data.amount)

    y -= 40

    # 🔷 Other Details
    details = [
        ("Packing", data.packing),
        ("Loading Port", data.loading_port),
        ("Destination Port", data.destination_port),
        ("Shipment", data.shipment),
        ("Seller’s Bank", data.sellers_bank),
        ("Account No.", data.account_no),
        ("Documents", data.documents),
        ("Payment Terms", data.payment_terms)
    ]
    for label, value in details:
        para = Paragraph(f"<b>{label}:</b> {value}", normal)
        w, h = para.wrap(width - 100, 30)
        para.drawOn(c, left_margin, y - h)
        y -= h + 5

    # 🔷 Arbitration
    arbitration_text = (
        "<b>Arbitration:</b><br/>"
        "In the event of any dispute between the parties arising out of this contract,<br/>"
        "all disputes shall be settled by arbitration through a sole arbitrator appointed by M/S Shraddha Impex.<br/>"
        "The place of arbitration shall be Indore, M.P., and the laws of India shall apply."
    )
    para = Paragraph(arbitration_text, normal)
    w, h = para.wrap(width - 100, 150)
    para.drawOn(c, left_margin, y - h)
    y -= h + 20

    # 🔷 Terms & Conditions
    terms_text = (
        "<b>Terms & Conditions:</b><br/>"
        "1) In case of port congestion/skippance of vessel or any other port disturbances, "
        "the supplier or exporter will not be liable for any claim.<br/>"
        "2) Quality approved at load port by independent surveyors is final and shall be acceptable by both parties. "
        "The seller will not be liable for any claim at destination port."
    )
    para = Paragraph(terms_text, normal)
    w, h = para.wrap(width - 100, 150)
    para.drawOn(c, left_margin, y - h)
    y -= h + 40

    # 🔷 Signature Lines
    c.setFont("Helvetica", 11)
    c.drawString(left_margin, y, "Accepted")
    y -= 40
    c.drawString(left_margin, y, "For, Seller")
    c.drawCentredString(width / 2, y, "For, Consignee")
    c.drawRightString(right_margin, y, "For, Notify Party")

    # ✅ Save PDF
    c.save()
    buffer.seek(0)
    return Response(
        content=buffer.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Agreement.pdf"}
    )
