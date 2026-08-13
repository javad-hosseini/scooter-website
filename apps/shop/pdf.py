# apps/shop/pdf.py

from io import BytesIO
from django.http import HttpResponse
from django.utils import timezone  # ← این رو اضافه کن
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from django.conf import settings

from .models import Order  # ← این رو اضافه کن


# ثبت فونت فارسی (اگر فونت موجود باشد)
def register_persian_font():
    try:
        # مسیر فونت را تنظیم کن
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Vazirmatn-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Vazirmatn', font_path))
            return 'Vazirmatn'
    except:
        pass
    return 'Helvetica'


def export_orders_pdf(queryset, user=None):
    """
    Export selected orders to PDF.
    """
    buffer = BytesIO()

    # ثبت فونت فارسی
    font_name = register_persian_font()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    styles = getSampleStyleSheet()

    # استایل عنوان
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=16,
        alignment=1,  # وسط‌چین
        spaceAfter=20,
    )

    # استایل متن معمولی
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        alignment=0,  # راست‌چین
    )

    # استایل هدر جدول
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        alignment=1,
        textColor=colors.white,
    )

    elements = []

    # ===== عنوان =====
    title = Paragraph("گزارش سفارشات", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    # ===== اطلاعات کاربر =====
    if user:
        # ===== اصلاح این خط =====
        now = timezone.now()  # ← استفاده از django.utils.timezone
        info_text = f"کاربر: {user.fullname or user.username} | تاریخ: {now.strftime('%Y/%m/%d %H:%M')}"
        info = Paragraph(info_text, normal_style)
        elements.append(info)
        elements.append(Spacer(1, 0.2 * inch))

    # ===== داده‌های جدول =====
    data = []

    # هدرها
    headers = [
        'شماره سفارش',
        'مشتری',
        'مبلغ کل',
        'وضعیت',
        'تاریخ',
    ]
    data.append(headers)

    # ردیف‌ها
    for order in queryset:
        row = [
            order.order_number or '-',
            order.user.fullname or order.user.username,
            f"{int(order.total):,} تومان",
            dict(Order.STATUS_CHOICES).get(order.status, order.status),
            order.created_at.strftime('%Y/%m/%d'),
        ]
        data.append(row)

    # ===== ایجاد جدول =====
    table = Table(data, colWidths=[1.2 * inch, 1.5 * inch, 1.2 * inch, 1 * inch, 1.2 * inch])

    # استایل جدول
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2F6FED')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F1F5F9')]),
    ]))

    elements.append(table)

    # ===== جمع کل =====
    total_sum = sum(order.total for order in queryset)
    summary_text = f"جمع کل سفارشات: {int(total_sum):,} تومان | تعداد سفارشات: {queryset.count()}"
    summary = Paragraph(summary_text, normal_style)
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(summary)

    # ===== ساخت PDF =====
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf