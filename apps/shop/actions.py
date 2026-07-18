# apps/shop/actions.py

from django.http import HttpResponse
from django.utils import timezone

from .pdf import export_orders_pdf
from .excel import export_orders_excel
from .models import Order


def export_selected_orders_to_pdf(modeladmin, request, queryset):
    """
    Export selected orders to PDF.
    """
    pdf = export_orders_pdf(queryset, request.user)

    response = HttpResponse(
        pdf,
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="orders_report_{timezone.now().strftime("%Y%m%d")}.pdf"'
    )

    return response


export_selected_orders_to_pdf.short_description = "📄 خروجی PDF از سفارشات انتخاب شده"


def export_selected_orders_to_excel(modeladmin, request, queryset):
    """
    Export selected orders to Excel.
    """
    workbook = export_orders_excel(queryset)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="orders_report_{timezone.now().strftime("%Y%m%d")}.xlsx"'
    )

    workbook.save(response)

    return response


export_selected_orders_to_excel.short_description = "📊 خروجی Excel از سفارشات انتخاب شده"