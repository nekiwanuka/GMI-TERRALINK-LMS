"""Reset application data and load a realistic demo dataset for logistics and sourcing."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from logistics.models import Client

User = get_user_model()

DEPARTMENT_LABELS = {
    "logistics": "Logistics",
    "sourcing": "Sourcing / Trade",
}
SUPPORTED_CURRENCIES = ("USD", "UGX")
DEFAULT_CURRENCY = "USD"


class Command(BaseCommand):
    help = (
        "Delete existing app data, keep superusers only, and seed a realistic demo "
        "dataset for both Logistics and Sourcing / Trade workflows."
    )

    def handle(self, *args, **options):
        seed_owner = self._get_seed_owner()

        self.stdout.write(self.style.WARNING("Clearing existing application data ..."))
        self._flush()

        self.stdout.write("Creating fresh seed dataset ...")
        clients = self._create_clients(seed_owner)
        suppliers = self._create_suppliers(seed_owner)
        loadings = self._create_loadings(seed_owner, clients)
        transits = self._create_transits(seed_owner, loadings)
        transactions = self._create_transactions(seed_owner, clients, loadings)
        sourcing_records = self._create_sourcing_records(seed_owner, transactions)
        proformas = self._create_proformas(seed_owner, transactions, loadings)
        final_invoices = self._create_final_invoices(seed_owner, transactions, loadings)
        logistics_payments = self._create_logistics_payments(
            seed_owner, loadings, final_invoices
        )
        trade_payments = self._create_trade_payments(
            seed_owner, transactions, final_invoices
        )
        inventory_items = self._create_inventory(seed_owner, suppliers, transactions)

        self.stdout.write(
            self.style.SUCCESS(
                "Seed complete. "
                f"Preserved {User.objects.filter(is_superuser=True).count()} superuser(s), "
                f"created {len(clients)} clients, {len(suppliers)} suppliers, "
                f"{len(loadings)} loadings, {len(transits)} transit record(s), "
                f"{len(transactions)} transactions, {len(sourcing_records)} sourcing record(s), "
                f"{len(proformas)} proformas, {len(final_invoices)} final invoices, "
                f"{len(logistics_payments)} logistics payment record(s), "
                f"{len(trade_payments)} trade payment record(s), and "
                f"{len(inventory_items)} inventory item(s)."
            )
        )

    def _get_seed_owner(self):
        superuser = User.objects.filter(is_superuser=True).order_by("id").first()
        if not superuser:
            raise CommandError(
                "No superuser found. Create a superuser before running seed_data."
            )
        return superuser

    def _flush(self):
        from logistics.models import (
            AuditLog,
            BillingCharge,
            BillingInvoice,
            BillingInvoiceLine,
            BillingPayment,
            CargoItemWorkflow,
            ContainerReturn,
            Document,
            DocumentArchive,
            DomainEvent,
            FinalInvoice,
            FulfillmentLine,
            FulfillmentOrder,
            InventoryItem,
            InventoryMovement,
            InventoryPosition,
            Loading,
            Notification,
            Payment,
            PaymentTransaction,
            ProformaInvoice,
            PurchaseOrder,
            Receipt,
            ShipmentLeg,
            ShipmentWorkflow,
            Sourcing,
            Supplier,
            SupplierProduct,
            Transaction,
            TransactionPaymentRecord,
            Transit,
            WorkflowTransitionLog,
        )

        deletion_order = [
            Notification,
            AuditLog,
            Receipt,
            BillingPayment,
            BillingInvoiceLine,
            BillingInvoice,
            BillingCharge,
            WorkflowTransitionLog,
            InventoryMovement,
            DomainEvent,
            InventoryPosition,
            CargoItemWorkflow,
            ShipmentWorkflow,
            TransactionPaymentRecord,
            ShipmentLeg,
            FulfillmentLine,
            FulfillmentOrder,
            PaymentTransaction,
            Payment,
            FinalInvoice,
            ProformaInvoice,
            Sourcing,
            DocumentArchive,
            Document,
            ContainerReturn,
            Transit,
            InventoryItem,
            SupplierProduct,
            Supplier,
            Transaction,
            Loading,
            Client,
        ]

        PurchaseOrder.objects.filter(parent_po__isnull=False).delete()
        PurchaseOrder.objects.filter(parent_po__isnull=True).delete()

        for model in deletion_order:
            model.objects.all().delete()

        User.objects.filter(is_superuser=False).delete()
        self.stdout.write(
            f"  Preserved {User.objects.filter(is_superuser=True).count()} superuser(s)."
        )

    def _create_clients(self, created_by):
        client_payloads = {
            "groupage_client": {
                "name": "Silverline Home Imports",
                "company_name": "Silverline Home Imports Ltd",
                "contact_person": "Christine Namutebi",
                "email": "imports@silverlinehome.com",
                "phone": "+256700411001",
                "address": "Plot 22 Bombo Road, Kampala",
                "country": "Uganda",
                "remarks": f"{DEPARTMENT_LABELS['logistics']} client using shared groupage freight from Guangzhou — furniture and home fittings.",
                "created_by": created_by,
            },
            "fcl_client": {
                "name": "Equator Build Holdings",
                "company_name": "Equator Build Holdings East Africa",
                "contact_person": "Robert Kizito",
                "email": "ops@equatorbuildholdings.com",
                "phone": "+256772321202",
                "address": "6th Street Industrial Area, Kampala",
                "country": "Uganda",
                "remarks": f"{DEPARTMENT_LABELS['logistics']} client for full container freight and project cargo — steel and construction materials.",
                "created_by": created_by,
            },
            "trade_retail": {
                "name": "Savannah Interiors",
                "company_name": "Savannah Interiors Ltd",
                "contact_person": "Patience Akello",
                "email": "procurement@savannahinteriors.com",
                "phone": "+256782531303",
                "address": "Kampala Road, Kampala",
                "country": "Uganda",
                "remarks": f"{DEPARTMENT_LABELS['sourcing']} client for lighting, shelving, and retail interior fittings.",
                "created_by": created_by,
            },
            "trade_medical": {
                "name": "Medicore Supplies Uganda",
                "company_name": "Medicore Supplies Uganda Limited",
                "contact_person": "Dr. Grace Nakato",
                "email": "sourcing@medicoresupplies.com",
                "phone": "+256751441404",
                "address": "Nakasero Medical Plaza, Kampala",
                "country": "Uganda",
                "remarks": f"{DEPARTMENT_LABELS['sourcing']} client for clinical consumables, diagnostics, and lab supplies.",
                "created_by": created_by,
            },
            "trade_agro": {
                "name": "GreenPath Agro Packaging",
                "company_name": "GreenPath Agro Packaging Uganda",
                "contact_person": "Samuel Okello",
                "email": "supply@greenpathagro.com",
                "phone": "+256774981505",
                "address": "Gulu Logistics Park, Gulu",
                "country": "Uganda",
                "remarks": f"{DEPARTMENT_LABELS['sourcing']} client for agro packaging materials and warehouse equipment.",
                "created_by": created_by,
            },
        }
        return {
            key: Client.objects.create(**payload)
            for key, payload in client_payloads.items()
        }

    def _create_suppliers(self, created_by):
        from logistics.models import Supplier, SupplierProduct

        supplier_payloads = {
            "furniture_supplier": {
                "name": "Guangzhou Smart Living Co.",
                "contact_person": "Leo Chen",
                "phone": "+86 177 0165 464",
                "email": "sales@smartlivinggz.cn",
                "address": "Baiyun District, Guangzhou, China",
                "supplies": "Lighting fixtures, retail shelves, home accessories",
                "min_order_quantity": Decimal("50"),
                "reference_unit_price": Decimal("42.50"),
                "notes": "Good lead times for mixed showroom and décor orders.",
                "created_by": created_by,
                "products": [
                    {
                        "product_name": "Warm LED Pendant Lamp",
                        "specifications": "Matte black, 24W, CE compliant",
                        "min_order_quantity": Decimal("80"),
                        "unit_price": Decimal("18.50"),
                        "resale_price": Decimal("27.00"),
                        "notes": "Good margin for retail fit-outs.",
                    },
                    {
                        "product_name": "Retail Gondola Shelf",
                        "specifications": "Double sided, powder coated, 1.8m",
                        "min_order_quantity": Decimal("20"),
                        "unit_price": Decimal("76.00"),
                        "resale_price": Decimal("110.00"),
                        "notes": "Flat-pack shipment available.",
                    },
                ],
            },
            "medical_supplier": {
                "name": "Shenzhen Meditech Supply",
                "contact_person": "Angela Wu",
                "phone": "+86 755 9088 1432",
                "email": "export@szmeditech.cn",
                "address": "Nanshan, Shenzhen, China",
                "supplies": "Diagnostic kits, gloves, rapid test consumables",
                "min_order_quantity": Decimal("100"),
                "reference_unit_price": Decimal("8.20"),
                "notes": "Responsive on regulated medical consumables.",
                "created_by": created_by,
                "products": [
                    {
                        "product_name": "Nitrile Examination Gloves",
                        "specifications": "Powder free, blue, 100 pcs/box",
                        "min_order_quantity": Decimal("500"),
                        "unit_price": Decimal("3.90"),
                        "resale_price": Decimal("5.60"),
                        "notes": "EN455 documentation available.",
                    },
                    {
                        "product_name": "Digital Infrared Thermometer",
                        "specifications": "Forehead type, backlit display",
                        "min_order_quantity": Decimal("100"),
                        "unit_price": Decimal("12.40"),
                        "resale_price": Decimal("17.80"),
                        "notes": "MOQ flexible for repeat buyers.",
                    },
                ],
            },
            "industrial_supplier": {
                "name": "Foshan Steel Works",
                "contact_person": "Kevin Liu",
                "phone": "+86 757 6631 9980",
                "email": "projects@foshansteelworks.cn",
                "address": "Foshan Industrial Zone, Guangdong, China",
                "supplies": "Structural steel fittings, warehouse racking accessories",
                "min_order_quantity": Decimal("10"),
                "reference_unit_price": Decimal("420.00"),
                "notes": "Suitable for FCL project cargo and warehouse builds.",
                "created_by": created_by,
                "products": [
                    {
                        "product_name": "Steel Rack Upright Set",
                        "specifications": "2.5m heavy-duty upright frame",
                        "min_order_quantity": Decimal("30"),
                        "unit_price": Decimal("41.00"),
                        "resale_price": Decimal("58.00"),
                        "notes": "Pairs with heavy duty beams.",
                    },
                ],
            },
        }

        suppliers = {}
        for key, payload in supplier_payloads.items():
            products = payload.pop("products")
            supplier = Supplier.objects.create(**payload)
            suppliers[key] = supplier
            for product in products:
                SupplierProduct.objects.create(
                    supplier=supplier,
                    created_by=created_by,
                    **product,
                )
        return suppliers

    def _create_loadings(self, created_by, clients):
        from logistics.models import Loading

        now = timezone.now()
        return {
            "groupage": Loading.objects.create(
                loading_id=Loading.generate_loading_id("GROUPAGE"),
                entry_type="GROUPAGE",
                client=clients["groupage_client"],
                loading_date=now - timedelta(days=4),
                item_description="Mixed lighting fixtures, décor accessories, and packed home goods",
                packages=48,
                weight=Decimal("3250.00"),
                cbm=Decimal("12.400"),
                container_size="lcl",
                warehouse_location="Rack G-12",
                groupage_note_number="GN-2026-041",
                origin="Guangzhou, China",
                destination="Kampala, Uganda",
                created_by=created_by,
            ),
            "fcl": Loading.objects.create(
                loading_id=Loading.generate_loading_id("FULL_CONTAINER"),
                entry_type="FULL_CONTAINER",
                client=clients["fcl_client"],
                loading_date=now - timedelta(days=9),
                item_description="Structural steel coils, fittings, and reinforced warehouse frames",
                packages=22,
                weight=Decimal("18200.00"),
                cbm=Decimal("28.750"),
                container_number="MSCU4821976",
                container_size="40ft_hc",
                warehouse_location="Yard A-04",
                bill_of_lading_number="BL-UG-2026-118",
                origin="Tianjin, China",
                destination="Kampala, Uganda",
                created_by=created_by,
            ),
        }

    def _create_transits(self, created_by, loadings):
        from logistics.models import Transit

        return [
            Transit.objects.create(
                loading=loadings["fcl"],
                vessel_name="MV Eastern Atlas",
                boarding_date=timezone.now() - timedelta(days=6),
                eta_kampala=timezone.now() + timedelta(days=11),
                status="in_transit",
                remarks="Container departed Mombasa and is on inland leg to Kampala.",
                created_by=created_by,
            )
        ]

    def _create_transactions(self, created_by, clients, loadings):
        from logistics.models import Transaction

        return {
            "groupage_freight": Transaction.objects.create(
                customer=clients["groupage_client"],
                source_loading=loadings["groupage"],
                status="PROFORMA_CREATED",
                description="Freight billing for LCL groupage cargo from Guangzhou.",
                notes="Auto-seeded logistics workflow for CBM-rated freight invoice.",
                estimated_delivery=timezone.localdate() + timedelta(days=14),
                created_by=created_by,
            ),
            "fcl_freight": Transaction.objects.create(
                customer=clients["fcl_client"],
                source_loading=loadings["fcl"],
                status="FINAL_INVOICE_CREATED",
                description="Freight billing for full container steel shipment.",
                notes="Auto-seeded logistics workflow with confirmed freight invoice.",
                estimated_delivery=timezone.localdate() + timedelta(days=10),
                created_by=created_by,
            ),
            "retail_trade": Transaction.objects.create(
                customer=clients["trade_retail"],
                status="PROFORMA_CREATED",
                description="Retail shelving and lighting sourcing request.",
                notes="Trade workflow for showroom fit-out procurement.",
                estimated_delivery=timezone.localdate() + timedelta(days=28),
                created_by=created_by,
            ),
            "medical_trade": Transaction.objects.create(
                customer=clients["trade_medical"],
                status="FINAL_INVOICE_CREATED",
                description="Medical consumables procurement and forwarding.",
                notes="Confirmed order awaiting additional payment collection.",
                estimated_delivery=timezone.localdate() + timedelta(days=21),
                created_by=created_by,
            ),
            "agro_trade": Transaction.objects.create(
                customer=clients["trade_agro"],
                status="PAID",
                description="Warehouse packaging materials and handling tools.",
                notes="Paid trade order ready for warehouse and fulfillment operations.",
                estimated_delivery=timezone.localdate() + timedelta(days=16),
                created_by=created_by,
            ),
        }

    def _create_sourcing_records(self, created_by, transactions):
        from logistics.models import Sourcing

        return [
            Sourcing.objects.create(
                transaction=transactions["retail_trade"],
                supplier_name="Guangzhou Smart Living Co.",
                supplier_contact="Leo Chen | sales@smartlivinggz.cn",
                item_details=[
                    {
                        "name": "Warm LED Pendant Lamp",
                        "quantity": "120",
                        "unit": "pcs",
                        "notes": "For branch showroom fit-out",
                    },
                    {
                        "name": "Retail Gondola Shelf",
                        "quantity": "24",
                        "unit": "sets",
                        "notes": "Black finish requested",
                    },
                ],
                unit_prices={
                    "Warm LED Pendant Lamp": "18.50",
                    "Retail Gondola Shelf": "76.00",
                },
                notes="Preferred supplier due to lead time and mixed-carton packing flexibility.",
                created_by=created_by,
            ),
            Sourcing.objects.create(
                transaction=transactions["medical_trade"],
                supplier_name="Shenzhen Meditech Supply",
                supplier_contact="Angela Wu | export@szmeditech.cn",
                item_details=[
                    {
                        "name": "Nitrile Examination Gloves",
                        "quantity": "1000",
                        "unit": "boxes",
                        "notes": "Powder free",
                    },
                    {
                        "name": "Digital Infrared Thermometer",
                        "quantity": "200",
                        "unit": "pcs",
                        "notes": "Hospital procurement batch",
                    },
                ],
                unit_prices={
                    "Nitrile Examination Gloves": "3.90",
                    "Digital Infrared Thermometer": "12.40",
                },
                notes="Regulatory documents shared and client has approved sampled units.",
                created_by=created_by,
            ),
        ]

    def _create_proformas(self, created_by, transactions, loadings):
        from logistics.models import ProformaInvoice

        today = timezone.localdate()
        return [
            ProformaInvoice.objects.create(
                transaction=transactions["groupage_freight"],
                loading=loadings["groupage"],
                items=[
                    {
                        "description": "Sea Freight – Groupage (LCL)",
                        "quantity": "12.400",
                        "unit": "CBM",
                        "unit_price": 145.0,
                        "sales_price": 1798.0,
                        "total": 1798.0,
                    },
                    {
                        "description": "Destination Handling",
                        "quantity": "1",
                        "unit": "Lot",
                        "unit_price": 280.0,
                        "sales_price": 280.0,
                        "total": 280.0,
                    },
                ],
                subtotal=Decimal("2078.00"),
                sourcing_fee=Decimal("180.00"),
                handling_fee=Decimal("95.00"),
                shipping_fee=Decimal("0.00"),
                validity_date=today + timedelta(days=21),
                status="DRAFT",
                created_by=created_by,
            ),
            ProformaInvoice.objects.create(
                transaction=transactions["fcl_freight"],
                loading=loadings["fcl"],
                items=[
                    {
                        "description": "Sea Freight – Full Container (40 FT High Cube)",
                        "quantity": "1",
                        "unit": "Container",
                        "unit_price": 6200.0,
                        "sales_price": 6200.0,
                        "total": 6200.0,
                    },
                    {
                        "description": "Port Handling and Clearance",
                        "quantity": "1",
                        "unit": "Lot",
                        "unit_price": 950.0,
                        "sales_price": 950.0,
                        "total": 950.0,
                    },
                ],
                subtotal=Decimal("7150.00"),
                sourcing_fee=Decimal("420.00"),
                handling_fee=Decimal("160.00"),
                shipping_fee=Decimal("0.00"),
                validity_date=today + timedelta(days=14),
                status="SENT",
                created_by=created_by,
            ),
            ProformaInvoice.objects.create(
                transaction=transactions["retail_trade"],
                items=[
                    {
                        "description": "Warm LED Pendant Lamp",
                        "quantity": "120",
                        "unit_price": 18.5,
                        "sales_price": 18.5,
                        "total": 2220.0,
                    },
                    {
                        "description": "Retail Gondola Shelf",
                        "quantity": "24",
                        "unit_price": 76.0,
                        "sales_price": 76.0,
                        "total": 1824.0,
                    },
                ],
                subtotal=Decimal("4044.00"),
                sourcing_fee=Decimal("250.00"),
                handling_fee=Decimal("160.00"),
                shipping_fee=Decimal("320.00"),
                validity_date=today + timedelta(days=30),
                status="DRAFT",
                supplier_name="Guangzhou Smart Living Co.",
                supplier_address="Baiyun District, Guangzhou, China",
                created_by=created_by,
            ),
            ProformaInvoice.objects.create(
                transaction=transactions["medical_trade"],
                items=[
                    {
                        "description": "Nitrile Examination Gloves",
                        "quantity": "1000",
                        "unit_price": 3.9,
                        "sales_price": 3.9,
                        "total": 3900.0,
                    },
                    {
                        "description": "Digital Infrared Thermometer",
                        "quantity": "200",
                        "unit_price": 12.4,
                        "sales_price": 12.4,
                        "total": 2480.0,
                    },
                ],
                subtotal=Decimal("6380.00"),
                sourcing_fee=Decimal("300.00"),
                handling_fee=Decimal("180.00"),
                shipping_fee=Decimal("450.00"),
                validity_date=today + timedelta(days=18),
                status="SENT",
                supplier_name="Shenzhen Meditech Supply",
                supplier_address="Nanshan, Shenzhen, China",
                created_by=created_by,
            ),
        ]

    def _create_final_invoices(self, created_by, transactions, loadings):
        from logistics.models import FinalInvoice

        return {
            "fcl_freight": FinalInvoice.objects.create(
                transaction=transactions["fcl_freight"],
                loading=loadings["fcl"],
                items=[
                    {
                        "description": "Sea Freight – Full Container (40 FT High Cube)",
                        "quantity": "1",
                        "amount": 6200.0,
                    },
                    {
                        "description": "Port Handling and Clearance",
                        "quantity": "1",
                        "amount": 950.0,
                    },
                ],
                subtotal=Decimal("7150.00"),
                sourcing_fee=Decimal("420.00"),
                shipping_cost=Decimal("0.00"),
                service_fee=Decimal("160.00"),
                total_amount=Decimal("7730.00"),
                currency=DEFAULT_CURRENCY,
                shipping_mode="SEA",
                route="Tianjin-Mombasa-Kampala",
                is_confirmed=True,
                confirmed_at=timezone.now() - timedelta(days=3),
                created_by=created_by,
            ),
            "medical_trade": FinalInvoice.objects.create(
                transaction=transactions["medical_trade"],
                items=[
                    {
                        "description": "Nitrile Examination Gloves",
                        "quantity": "1000",
                        "amount": 3900.0,
                    },
                    {
                        "description": "Digital Infrared Thermometer",
                        "quantity": "200",
                        "amount": 2480.0,
                    },
                ],
                subtotal=Decimal("6380.00"),
                sourcing_fee=Decimal("300.00"),
                shipping_cost=Decimal("450.00"),
                service_fee=Decimal("180.00"),
                total_amount=Decimal("7310.00"),
                currency=DEFAULT_CURRENCY,
                shipping_mode="AIR",
                route="Shenzhen-Entebbe-Kampala",
                is_confirmed=True,
                confirmed_at=timezone.now() - timedelta(days=2),
                created_by=created_by,
            ),
            "agro_trade": FinalInvoice.objects.create(
                transaction=transactions["agro_trade"],
                items=[
                    {
                        "description": "Warehouse Stretch Film Rolls",
                        "quantity": "200",
                        "amount": 1800.0,
                    },
                    {
                        "description": "Heavy Duty Packing Tape Cartons",
                        "quantity": "120",
                        "amount": 960.0,
                    },
                    {
                        "description": "Steel Rack Upright Set",
                        "quantity": "40",
                        "amount": 1640.0,
                    },
                ],
                subtotal=Decimal("4400.00"),
                sourcing_fee=Decimal("220.00"),
                shipping_cost=Decimal("340.00"),
                service_fee=Decimal("140.00"),
                total_amount=Decimal("5100.00"),
                currency=DEFAULT_CURRENCY,
                shipping_mode="SEA",
                route="Guangzhou-Mombasa-Gulu",
                is_confirmed=True,
                confirmed_at=timezone.now() - timedelta(days=5),
                created_by=created_by,
            ),
        }

    def _create_logistics_payments(self, created_by, loadings, final_invoices):
        from logistics.models import Payment

        return [
            Payment.objects.create(
                loading=loadings["fcl"],
                final_invoice=final_invoices["fcl_freight"],
                billing_basis="manual",
                amount_charged=Decimal("7730.00"),
                amount_paid=Decimal("0.00"),
                balance=Decimal("7730.00"),
                created_by=created_by,
            )
        ]

    def _create_trade_payments(self, created_by, transactions, final_invoices):
        from logistics.models import Transaction, TransactionPaymentRecord

        payments = [
            TransactionPaymentRecord.objects.create(
                transaction=transactions["medical_trade"],
                final_invoice=final_invoices["medical_trade"],
                amount_due_snapshot=Decimal("7310.00"),
                is_full_payment=False,
                amount=Decimal("3000.00"),
                currency=DEFAULT_CURRENCY,
                cash_received=Decimal("3200.00"),
                balance_after=Decimal("4310.00"),
                payment_date=timezone.now() - timedelta(days=1),
                payment_method="cash",
                reference="MED-DEP-3000",
                notes="Initial deposit received pending balance settlement.",
                created_by=created_by,
            ),
            TransactionPaymentRecord.objects.create(
                transaction=transactions["agro_trade"],
                final_invoice=final_invoices["agro_trade"],
                amount_due_snapshot=Decimal("5100.00"),
                is_full_payment=True,
                amount=Decimal("5100.00"),
                currency=DEFAULT_CURRENCY,
                cash_received=None,
                balance_after=Decimal("0.00"),
                payment_date=timezone.now() - timedelta(days=4),
                payment_method="bank_transfer",
                reference="NAE-TRF-5100",
                notes="Client settled invoice in full via bank transfer.",
                created_by=created_by,
            ),
        ]

        Transaction.objects.filter(pk=transactions["medical_trade"].pk).update(
            status="FINAL_INVOICE_CREATED"
        )
        Transaction.objects.filter(pk=transactions["agro_trade"].pk).update(
            status="PAID"
        )
        return payments

    def _create_inventory(self, created_by, suppliers, transactions):
        from logistics.models import InventoryItem

        return [
            InventoryItem.objects.create(
                item_code="INV-STRETCH-001",
                item_name="Warehouse Stretch Film Rolls",
                description="Industrial wrap rolls for palletized export packing.",
                quantity_purchased=200,
                quantity_shipped=40,
                transaction=transactions["agro_trade"],
                supplier=suppliers["industrial_supplier"],
                updated_by=created_by,
            ),
            InventoryItem.objects.create(
                item_code="INV-TAPE-002",
                item_name="Heavy Duty Packing Tape Cartons",
                description="Clear tape cartons reserved for packaging team.",
                quantity_purchased=120,
                quantity_shipped=20,
                transaction=transactions["agro_trade"],
                supplier=suppliers["industrial_supplier"],
                updated_by=created_by,
            ),
            InventoryItem.objects.create(
                item_code="INV-SHELF-003",
                item_name="Retail Gondola Shelf",
                description="Showroom shelving sets awaiting branch allocation.",
                quantity_purchased=24,
                quantity_shipped=0,
                transaction=transactions["retail_trade"],
                supplier=suppliers["furniture_supplier"],
                updated_by=created_by,
            ),
        ]
