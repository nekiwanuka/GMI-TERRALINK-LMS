"""
Logistics models package.

This package was split out of the original ``models.py`` for readability while
keeping the public import surface identical:

    from logistics.models import Client, Commission, ...

Internally:
    - ``_legacy``    : the bulk of the historical models (untouched).
    - ``commission`` : the Commission ledger (extracted as the first proof
      of the split mechanism).

To extract more groups, move the relevant classes into a new module file
and re-export them below. Do not change ``app_label`` and do not move models
across Django apps without a managed migration plan.
"""

# Re-export everything from the historical module so existing imports keep
# working (``from logistics.models import X`` still resolves to the same class).
from ._legacy import *  # noqa: F401,F403
from ._legacy import (  # noqa: F401  explicit re-exports for IDE/autocomplete
    AuditLog,
    BillingCharge,
    BillingInvoice,
    BillingInvoiceLine,
    BillingPayment,
    CargoItemWorkflow,
    Client,
    ContainerReturn,
    CustomUser,
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
    SupplierPayment,
    Transaction,
    TransactionPaymentRecord,
    Transit,
    WorkflowTransitionLog,
)

# Private helpers — explicitly re-exported because ``import *`` skips
# leading-underscore names. ``views.py`` consumes the PDF helpers and
# migration 0003 references ``logistics.models._random_code`` as a default
# callable; both paths must keep resolving here.
from ._legacy import (  # noqa: F401
    _draw_international_terms_footer,
    _draw_standard_doc_header,
    _random_code,
    _random_digits,
)

# Commission lives in its own file as the first extracted module — proves the
# split pattern works without touching migrations or any callers.
from .commission import COMMISSION_CURRENCY_CHOICES, Commission  # noqa: F401

# Proof of Delivery — close-out artifact for both business lines.
from .proof_of_delivery import ProofOfDelivery  # noqa: F401

# Reusable uploaded staff signatures and document signing audit trail.
from .signatures import DocumentSignature, SignatureProfile  # noqa: F401
