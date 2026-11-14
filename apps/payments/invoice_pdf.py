"""
توليد فاتورة/إيصال PDF بخط عربي (Almarai) — بدون الاعتماد على أي سكربت.
RTL يدوي: كل نص عربي يُعاد تشكيله (arabic-reshaper) ويُعكس اتجاهه (python-bidi).
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from arabic_reshaper import reshape
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
NAVY = colors.HexColor("#0e2a47")
NAVY_LIGHT = colors.HexColor("#17405f")
GOLD = colors.HexColor("#d4af37")
GREY = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f4f5f7")

_fonts_registered = False


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont("Almarai", str(FONT_DIR / "Almarai-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Almarai-Bold", str(FONT_DIR / "Almarai-Bold.ttf")))
    _fonts_registered = True


def ar(text: str) -> str:
    """أعد تشكيل النص العربي ليظهر صحيحًا في PDF لاتيني الاتجاه."""
    if not text:
        return ""
    # القاعدة: الأرقام اللاتينية وشبه اللاتينية تُترك على حدة داخل bidi
    return get_display(reshape(str(text)))


def _draw_header(c: canvas.Canvas, width, center_name: str, address: str, phone: str):
    c.setFillColor(NAVY)
    c.rect(0, A4[1] - 34 * mm, width, 34 * mm, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.rect(0, A4[1] - 34.8 * mm, width, 0.8 * mm, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Almarai-Bold", 19)
    c.drawRightString(width - 15 * mm, A4[1] - 14 * mm, ar(center_name))
    c.setFillColor(colors.HexColor("#bcd0e0"))
    c.setFont("Almarai", 8)
    c.drawRightString(width - 15 * mm, A4[1] - 20.5 * mm, ar(address))
    c.drawRightString(width - 15 * mm, A4[1] - 25.5 * mm, ar(f"ت: {phone}"))
    c.setFillColor(GOLD)
    c.setFont("Almarai-Bold", 11)
    c.drawString(15 * mm, A4[1] - 14 * mm, "RECEIPT")
    c.setFont("Almarai", 8)
    c.drawString(15 * mm, A4[1] - 20.5 * mm, "Official payment receipt")


def _draw_row(c, y, width, label, value, *, bold=False, label_color=GREY, value_color=NAVY):
    c.setFillColor(label_color)
    c.setFont("Almarai", 9)
    c.drawRightString(width - 15 * mm, y, ar(label))
    c.setFillColor(value_color)
    c.setFont("Almarai-Bold" if bold else "Almarai", 10)
    c.drawRightString(width - 60 * mm, y, ar(value))


def render_invoice_pdf(payment, invoice, *, center_name: str, address: str, phone: str, member_name: str, membership_number: str) -> bytes:
    _register_fonts()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    _draw_header(c, width, center_name, address, phone)

    # عنوان الفاتورة
    y = height - 48 * mm
    c.setFillColor(NAVY)
    c.setFont("Almarai-Bold", 17)
    c.drawRightString(width - 15 * mm, y, ar("إيصال دفع"))
    c.setFillColor(GREY)
    c.setFont("Almarai", 9)
    c.drawRightString(width - 15 * mm, y - 6 * mm, ar("Payment Receipt"))

    # بيانات الفاتورة
    y -= 18 * mm
    issued = (invoice.issued_at if invoice else None) or payment.paid_at or payment.created_at
    rows = [
        ("رقم الفاتورة", invoice.number if invoice else "—"),
        ("كود الطلب", payment.reference),
        ("تاريخ الإصدار", issued.strftime("%Y-%m-%d %H:%M")),
        ("حالة الدفع", "مدفوع" if payment.status == "paid" else payment.get_status_display()),
    ]
    for label, value in rows:
        _draw_row(c, y, width, label, value, bold=(label == "رقم الفاتورة"))
        y -= 8.2 * mm

    # بيانات العضو
    y -= 4 * mm
    c.setFillColor(LIGHT)
    c.roundRect(15 * mm, y - 14 * mm, width - 30 * mm, 15 * mm, 4, stroke=0, fill=1)
    _draw_row(c, y - 3 * mm, width, "العضو", member_name, bold=True)
    _draw_row(c, y - 9.5 * mm, width, "رقم العضوية", membership_number)
    _draw_row(c, y - 13.5 * mm - 3 * mm, width, "الموبايل", payment.member.phone if payment.member_id else "—")

    # جدول البيان
    y -= 28 * mm
    table_top = y
    header_h = 9 * mm
    c.setFillColor(NAVY_LIGHT)
    c.roundRect(15 * mm, table_top - header_h, width - 30 * mm, header_h, 3, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Almarai-Bold", 9)
    c.drawRightString(width - 20 * mm, table_top - 6 * mm, ar("البيان"))
    c.drawRightString(120 * mm, table_top - 6 * mm, ar("القيمة"))
    c.drawRightString(45 * mm, table_top - 6 * mm, ar("النوع"))

    kind_label = payment.get_kind_display()
    desc = payment.note or kind_label
    if payment.membership_id:
        desc = f"{payment.membership.membership_type.name_ar} — {payment.membership.membership_type.duration_months} شهر"
    row_h = 12 * mm
    c.setFillColor(colors.white)
    c.rect(15 * mm, table_top - header_h - row_h, width - 30 * mm, row_h, stroke=0, fill=1)
    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.rect(15 * mm, table_top - header_h - row_h, width - 30 * mm, row_h, stroke=1, fill=0)
    c.setFillColor(NAVY)
    c.setFont("Almarai", 9.5)
    c.drawRightString(width - 20 * mm, table_top - header_h - 7.5 * mm, ar(desc))
    c.drawRightString(120 * mm, table_top - header_h - 7.5 * mm, ar(f"{payment.amount:.2f} ج"))
    c.drawRightString(45 * mm, table_top - header_h - 7.5 * mm, ar(kind_label))

    # الإجمالي
    total_y = table_top - header_h - row_h - 14 * mm
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.6)
    c.roundRect(15 * mm, total_y - 4 * mm, width - 30 * mm, 14 * mm, 4, stroke=1, fill=0)
    c.setFillColor(GREY)
    c.setFont("Almarai", 9)
    c.drawRightString(width - 20 * mm, total_y + 3 * mm, ar("الإجمالي المدفوع"))
    c.setFillColor(NAVY)
    c.setFont("Almarai-Bold", 15)
    c.drawRightString(width - 20 * mm, total_y - 3 * mm, ar(f"{payment.amount:.2f} جنيه مصري"))

    # تذييل
    c.setFillColor(GREY)
    c.setFont("Almarai", 8)
    c.drawCentredString(width / 2, 18 * mm, ar("هذا الإيصال مستند رسمي صادر عن المركز ويُعتد به في السجلات المالية."))
    c.drawCentredString(width / 2, 13 * mm, ar("للاستعلام: تواصل مع الاستقبال مع ذكر كود الطلب."))
    c.setFillColor(GOLD)
    c.rect(0, 0, width, 5 * mm, stroke=0, fill=1)

    c.showPage()
    c.save()
    return buf.getvalue()
