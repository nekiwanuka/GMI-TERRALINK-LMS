"""Display helpers for department-coded business document references."""


def _has_related_object(document, relation_name):
    try:
        return getattr(document, relation_name) is not None
    except Exception:
        return False


def _has_related_id(document, relation_name):
    return bool(getattr(document, f"{relation_name}_id", None))


def document_department_code(document):
    """Return the display department code for a business document."""
    if document is None:
        return "SRC"

    if _has_related_id(document, "logistics_payment"):
        return "LOG"
    if _has_related_object(document, "logistics_payment"):
        return "LOG"

    if _has_related_id(document, "loading"):
        return "LOG"
    if _has_related_object(document, "loading"):
        return "LOG"

    final_invoice = getattr(document, "final_invoice", None)
    if final_invoice is not None:
        return document_department_code(final_invoice)

    transaction = getattr(document, "transaction", None)
    if transaction is not None and (
        _has_related_id(transaction, "source_loading")
        or _has_related_object(transaction, "source_loading")
    ):
        return "LOG"

    sourcing_payment = getattr(document, "sourcing_payment", None)
    if sourcing_payment is not None:
        return document_department_code(sourcing_payment)
    if _has_related_id(document, "sourcing_payment"):
        return "SRC"

    return "SRC"


def display_document_number(document, document_type):
    """Build a display-only document reference such as LOG-PI-12."""
    if document is None:
        return "-"

    document_type = (document_type or "").strip().upper()
    department_code = document_department_code(document)

    if document_type == "RCT":
        raw_number = getattr(document, "receipt_number", None) or getattr(
            document, "pk", None
        )
    else:
        raw_number = getattr(document, "pk", None) or getattr(document, "id", None)

    if not raw_number:
        return "-"
    raw_number = str(raw_number)
    duplicate_prefix = f"{document_type}-"
    if raw_number.upper().startswith(duplicate_prefix):
        raw_number = raw_number[len(duplicate_prefix) :]
    return f"{department_code}-{document_type}-{raw_number}"


def display_document_slug(document, document_type):
    """Return a filesystem-friendly lowercase document reference."""
    return display_document_number(document, document_type).lower().replace("-", "_")
