"""Director-level reporting services for finance and transaction KPIs."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.utils import timezone

from logistics.models import (
    FinalInvoice,
    ProformaInvoice,
    PurchaseOrder,
    Sourcing,
    Transaction,
    TransactionPaymentRecord,
    Transit,
)


class DirectorReportingService:
    """Aggregates transaction and invoicing metrics for executive reports."""

    TRADE_PIPELINE_GROUPS = (
        (
            "Inquiry Intake",
            ["RECEIVED", "CLEANED", "SENT_TO_SOURCING"],
        ),
        (
            "Quotation Stage",
            ["QUOTED", "PROFORMA_CREATED", "PROFORMA_SENT"],
        ),
        (
            "Confirmed Stage",
            ["CONFIRMED", "FINAL_INVOICE_CREATED"],
        ),
        (
            "Paid Stage",
            ["PAID"],
        ),
        (
            "Fulfilment",
            ["SHIPPED", "DELIVERED"],
        ),
    )

    @staticmethod
    def total_revenue():
        return (
            FinalInvoice.objects.filter(is_confirmed=True, transaction__status="PAID")
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or 0
        )

    @staticmethod
    def outstanding_balances():
        return (
            FinalInvoice.objects.filter(is_confirmed=True)
            .exclude(transaction__status="PAID")
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or 0
        )

    @staticmethod
    def transactions_per_status():
        rows = (
            Transaction.objects.values("status")
            .annotate(total=Count("id"))
            .order_by("status")
        )
        return {row["status"]: row["total"] for row in rows}

    @staticmethod
    def revenue_trends(days=90):
        start = timezone.now() - timedelta(days=days)
        base = FinalInvoice.objects.filter(
            is_confirmed=True,
            transaction__status="PAID",
            created_at__gte=start,
        )

        daily = list(
            base.annotate(period=TruncDay("created_at"))
            .values("period")
            .annotate(total=Sum("total_amount"))
            .order_by("period")
        )
        weekly = list(
            base.annotate(period=TruncWeek("created_at"))
            .values("period")
            .annotate(total=Sum("total_amount"))
            .order_by("period")
        )
        monthly = list(
            base.annotate(period=TruncMonth("created_at"))
            .values("period")
            .annotate(total=Sum("total_amount"))
            .order_by("period")
        )
        return {"daily": daily, "weekly": weekly, "monthly": monthly}

    @staticmethod
    def conversion_rate():
        inquiry_count = Transaction.objects.count()
        confirmed_count = Transaction.objects.filter(
            status__in=[
                "CONFIRMED",
                "FINAL_INVOICE_CREATED",
                "PAID",
                "SHIPPED",
                "DELIVERED",
            ]
        ).count()
        if inquiry_count == 0:
            return {"inquiries": 0, "confirmed": 0, "rate": 0}
        rate = (confirmed_count / inquiry_count) * 100
        return {
            "inquiries": inquiry_count,
            "confirmed": confirmed_count,
            "rate": round(rate, 2),
        }

    @staticmethod
    def top_clients(limit=5):
        return list(
            Transaction.objects.values("customer__name")
            .annotate(
                total_transactions=Count("id"),
                confirmed_orders=Count(
                    "id",
                    filter=Q(
                        status__in=[
                            "CONFIRMED",
                            "FINAL_INVOICE_CREATED",
                            "PAID",
                            "SHIPPED",
                            "DELIVERED",
                        ]
                    ),
                ),
            )
            .order_by("-total_transactions")[:limit]
        )

    @staticmethod
    def active_shipments_count():
        return Transit.objects.filter(status__in=["awaiting", "in_transit"]).count()

    @staticmethod
    def profit_estimate():
        revenue = FinalInvoice.objects.filter(is_confirmed=True).aggregate(
            total=Sum("total_amount")
        ).get("total") or Decimal("0")

        cost_total = Decimal("0")
        for record in Sourcing.objects.only("unit_prices"):
            unit_prices = record.unit_prices or {}
            if isinstance(unit_prices, dict):
                values = unit_prices.values()
            elif isinstance(unit_prices, list):
                values = unit_prices
            else:
                values = []
            for value in values:
                try:
                    cost_total += Decimal(str(value))
                except (InvalidOperation, TypeError, ValueError):
                    continue
        return revenue - cost_total

    @staticmethod
    def commission_totals():
        """Total commission earned grouped by currency."""
        from logistics.models import Commission

        rows = (
            Commission.objects.values("currency")
            .annotate(total=Sum("amount"), entries=Count("id"))
            .order_by("currency")
        )
        return [
            {
                "currency": row["currency"],
                "total": float(row["total"] or 0),
                "entries": row["entries"],
            }
            for row in rows
        ]

    @staticmethod
    def financial_totals():
        """Aggregated financial summary for reports dashboard."""
        total_revenue = FinalInvoice.objects.filter(
            is_confirmed=True, transaction__status="PAID"
        ).aggregate(total=Sum("total_amount")).get("total") or Decimal("0")
        outstanding = FinalInvoice.objects.filter(is_confirmed=True).exclude(
            transaction__status="PAID"
        ).aggregate(total=Sum("total_amount")).get("total") or Decimal("0")
        return {
            "total_revenue": float(total_revenue),
            "outstanding_balance": float(outstanding),
        }

    @staticmethod
    def revenue_trend(months=6):
        """Returns (labels, values) lists for a monthly revenue bar chart."""
        from datetime import date
        import calendar

        today = timezone.now().date()
        labels = []
        values = []
        for i in range(months - 1, -1, -1):
            # calculate year/month for offset i months back
            month = (today.month - i - 1) % 12 + 1
            year = today.year - ((today.month - i - 1) // 12)
            labels.append(f"{calendar.month_abbr[month]} {year}")
            total = (
                FinalInvoice.objects.filter(
                    is_confirmed=True,
                    transaction__status="PAID",
                    created_at__year=year,
                    created_at__month=month,
                )
                .aggregate(total=Sum("total_amount"))
                .get("total")
                or 0
            )
            values.append(float(total))
        return labels, values

    @staticmethod
    def transaction_status_breakdown():
        """Returns (labels, values) lists for a status pie/bar chart."""
        rows = (
            Transaction.objects.values("status")
            .annotate(total=Count("id"))
            .order_by("status")
        )
        labels = [r["status"].replace("_", " ").title() for r in rows]
        values = [r["total"] for r in rows]
        return labels, values

    @staticmethod
    def trade_activity_summary():
        """Headline sourcing and trade metrics for the director dashboard."""
        return {
            "sourcing_records": Sourcing.objects.count(),
            "active_sourcing_transactions": Transaction.objects.filter(
                status__in=[
                    "SENT_TO_SOURCING",
                    "QUOTED",
                    "PROFORMA_CREATED",
                    "PROFORMA_SENT",
                ]
            ).count(),
            "proformas_sent": ProformaInvoice.objects.filter(status="SENT").count(),
            "draft_proformas": ProformaInvoice.objects.filter(status="DRAFT").count(),
            "final_invoices": FinalInvoice.objects.count(),
            "purchase_orders": PurchaseOrder.objects.count(),
            "trade_payment_records": TransactionPaymentRecord.objects.count(),
            "paid_transactions": Transaction.objects.filter(status="PAID").count(),
        }

    @classmethod
    def trade_pipeline_breakdown(cls):
        """Grouped trade workflow counts for a pipeline chart."""
        labels = []
        values = []
        for label, statuses in cls.TRADE_PIPELINE_GROUPS:
            labels.append(label)
            values.append(Transaction.objects.filter(status__in=statuses).count())
        return labels, values

    @staticmethod
    def sourcing_activity_by_supplier(limit=6):
        """Top suppliers by sourcing record count."""
        return list(
            Sourcing.objects.exclude(supplier_name="")
            .values("supplier_name")
            .annotate(total_records=Count("id"))
            .order_by("-total_records", "supplier_name")[:limit]
        )

    @staticmethod
    def sourcing_activity_by_supplier_chart(limit=6):
        """Chart-friendly supplier activity split."""
        rows = DirectorReportingService.sourcing_activity_by_supplier(limit=limit)
        labels = [row["supplier_name"] for row in rows]
        values = [row["total_records"] for row in rows]
        return labels, values

    @staticmethod
    def recent_sourcing_activity(limit=6):
        """Latest sourcing records with transaction and client context."""
        return list(
            Sourcing.objects.select_related(
                "transaction__customer", "created_by"
            ).order_by("-created_at")[:limit]
        )
