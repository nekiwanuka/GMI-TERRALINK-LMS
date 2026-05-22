"""
Purchase Inquiry (PI) document parser for GMI TERRALINK.

Parses structured text extracted from a client PI document (PDF / Word / TXT)
and returns a normalised dict with the following keys:

    {
        "client_name":     str,
        "contact_person":  str,
        "phone":           str,
        "email":           str,
        "address":         str,
        "subject":         str,
        "items":           [{"name": str}, ...],
        "requirements":    [str, ...],
        "deadline":        str,
        "body_summary":    str,
    }

All fields are best-effort; missing fields default to empty string / empty list.
"""

import re
from decimal import Decimal, InvalidOperation

# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


def _first_match(patterns, text, group=1, flags=re.IGNORECASE):
    for pattern in patterns:
        m = re.search(pattern, text, flags)
        if m:
            return m.group(group).strip()
    return ""


def _extract_bullets(text):
    """
    Pull lines that look like bullet items:
      • Bullet text
      - Bullet text
      * Bullet text
      ▪ Bullet text
      Any line following "interested in" / "request for" context blocks.
    """
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        # Unicode bullets, ASCII dash bullets, asterisks, PDF Wingdings bullets
        _BULLET_CHARS = (
            r"\u2022\u2023\u25e6\u2043\u2219\-\*\u25aa\u25ab\u25cf\uf0b7\uf0a7\u00b7"
        )
        if re.match(rf"^[{_BULLET_CHARS}]\s*.+", stripped):
            # Remove leading bullet char and whitespace
            item = re.sub(
                rf"^[{_BULLET_CHARS}]\s*",
                "",
                stripped,
            )
            if len(item) > 3:
                # Skip lines that look like "Field: Value" (contact/address block)
                if not re.match(r"^[\w][\w\s]{1,25}:\s+.{3,}", item):
                    bullets.append(item.strip())
    return bullets


def _extract_requirements(text):
    """
    Look for bullets that appear in a 'requirements / quotation includes' section.
    """
    requirements = []
    in_req_section = False
    req_trigger = re.compile(
        r"(quotation includes|please include|requirements|specifications|kindly request)",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        stripped = line.strip()
        if req_trigger.search(stripped):
            in_req_section = True
            continue
        if in_req_section:
            # A blank line or a paragraph-looking line exits the section
            if not stripped:
                in_req_section = False
                continue
            _B = r"\u2022\u2023\u25e6\u2043\u2219\-\*\u25aa\u25ab\u25cf\uf0b7\uf0a7\u00b7"
            if re.match(rf"^[{_B}]\s*.+", stripped):
                req = re.sub(rf"^[{_B}]\s*", "", stripped)
                req = req.strip()
                # Skip "Field: Value" lines (contact block repeated on page 2)
                if req and not re.match(r"^[\w][\w\s]{1,25}:\s+.{3,}", req):
                    requirements.append(req)
    return requirements


def _split_bullet_sections(text):
    """
    Heuristic: identify two bullet groups – items wanted vs requirements.
    Items-wanted bullets typically appear before the requirements block.
    Strategy: collect ALL bullets, then split at the first 'requirements' bullet
    (which usually starts with 'Detailed', 'Quality', 'Delivery', 'Payment', 'Warranty').
    """
    req_words = re.compile(
        r"^(Detailed|Quality|Delivery|Payment|Warranty|After.sales|ISO|Credit|Timeline)",
        re.IGNORECASE,
    )
    all_bullets = _extract_bullets(text)
    items, requirements = [], []
    in_req = False
    for b in all_bullets:
        if req_words.match(b):
            in_req = True
        if in_req:
            requirements.append(b)
        else:
            items.append(b)
    return items, requirements


def _money_to_decimal(value):
    cleaned = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _looks_like_header_or_contact(line):
    lowered = line.lower()
    header_words = {
        "description",
        "item",
        "items",
        "product",
        "qty",
        "quantity",
        "unit",
        "price",
        "amount",
        "total",
        "subtotal",
    }
    if sum(1 for word in header_words if word in lowered) >= 3:
        return True
    return bool(
        re.search(
            r"\b(invoice|proforma|bill\s+to|ship\s+to|customer|client|supplier|address|email|phone|tel|date|no\.|number)\b",
            lowered,
        )
        and not re.search(r"\d+(?:[.,]\d{2})", lowered)
    )


def _parse_table_line(line):
    stripped = re.sub(r"\s+", " ", line.strip())
    if len(stripped) < 5 or _looks_like_header_or_contact(stripped):
        return None

    money_pattern = r"(?:USD|US\$|\$|UGX|CNY|RMB)?\s*\d[\d,]*(?:\.\d{1,2})?"
    quantity_pattern = r"\d+(?:\.\d+)?"
    match = re.match(
        rf"^(?P<name>.+?)\s+(?P<quantity>{quantity_pattern})\s*(?P<unit>[A-Za-z]{{1,12}})?\s+(?P<unit_price>{money_pattern})\s+(?P<total>{money_pattern})$",
        stripped,
        re.IGNORECASE,
    )
    if match:
        name = re.sub(r"^\d+\s+", "", match.group("name").strip(" -:,;"))
        if not name:
            return None
        unit_price = _money_to_decimal(match.group("unit_price"))
        total = _money_to_decimal(match.group("total"))
        item = {
            "name": name,
            "description": name,
            "quantity": match.group("quantity"),
        }
        unit = (match.group("unit") or "").strip()
        if unit:
            item["unit"] = unit
        if unit_price is not None:
            item["unit_price"] = float(unit_price)
            item["amount"] = float(unit_price)
        if total is not None:
            item["total"] = float(total)
        return item

    columns = [part.strip() for part in re.split(r"\t|\s{2,}|\|", line) if part.strip()]
    if len(columns) < 3:
        return None
    total = _money_to_decimal(columns[-1])
    if total is None:
        return None
    unit_price = _money_to_decimal(columns[-2]) if len(columns) >= 4 else total
    quantity = ""
    unit = ""
    name_columns = columns[:-2] if len(columns) >= 4 else columns[:-1]
    if len(name_columns) >= 2 and re.fullmatch(quantity_pattern, name_columns[-1]):
        quantity = name_columns[-1]
        name_columns = name_columns[:-1]
    if len(name_columns) >= 2 and re.fullmatch(r"[A-Za-z]{1,12}", name_columns[-1]):
        unit = name_columns[-1]
        name_columns = name_columns[:-1]
    name = re.sub(r"^\d+\s+", "", " ".join(name_columns).strip(" -:,;"))
    if not name:
        return None
    item = {"name": name, "description": name, "total": float(total)}
    if quantity:
        item["quantity"] = quantity
    if unit:
        item["unit"] = unit
    if unit_price is not None:
        item["unit_price"] = float(unit_price)
        item["amount"] = float(unit_price)
    return item


def _extract_invoice_line_items(text):
    items = []
    seen = set()
    for raw_line in text.splitlines():
        item = _parse_table_line(raw_line)
        if not item:
            continue
        key = (
            item.get("name", "").lower(),
            str(item.get("quantity", "")),
            str(item.get("unit_price", "")),
            str(item.get("total", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return items


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def parse_purchase_inquiry(text: str) -> dict:
    """
    Parse raw extracted text from a PI document.
    Returns a structured dict with client details, items, requirements, deadline.
    """
    result = {
        "client_name": "",
        "contact_person": "",
        "phone": "",
        "email": "",
        "address": "",
        "subject": "",
        "items": [],
        "requirements": [],
        "deadline": "",
        "body_summary": "",
    }

    if not text:
        return result

    # ── Client / Sender details ──────────────────
    result["client_name"] = _first_match(
        [
            r"(?:Hotel|Company|Organisation|Organization|Firm|Business|School|Hospital|Client)\s+Name\s*[:\-]\s*(.+)",
            r"(?:From|Sender)\s*[:\-]\s*(.+)",
        ],
        text,
    )

    result["contact_person"] = _first_match(
        [
            r"Contact\s+Person\s*[:\-]\s*(.+)",
            r"Attention\s*[:\-]\s*(.+)",
            r"Sincerely,?\s*(.+?)(?:\n|Procurement|Manager|Director|Officer)",
        ],
        text,
    )

    result["phone"] = _first_match(
        [
            r"Phone\s*[:\-]\s*(\+?[\d\s\-\(\)]+)",
            r"Tel(?:ephone)?\s*[:\-]\s*(\+?[\d\s\-\(\)]+)",
        ],
        text,
    )
    # Trim trailing whitespace from phone
    if result["phone"]:
        result["phone"] = result["phone"].strip()

    result["email"] = _first_match(
        [r"Email\s*[:\-]\s*([\w.\-+]+@[\w.\-]+\.\w+)", r"([\w.\-+]+@[\w.\-]+\.\w+)"],
        text,
    )

    result["address"] = _first_match(
        [
            r"Address\s*[:\-]\s*(.+)",
            r"(?:Located at|Based at|Location)\s*[:\-]\s*(.+)",
        ],
        text,
    )

    # ── Subject ──────────────────────────────────
    result["subject"] = _first_match(
        [
            r"Subject\s*[:\-]\s*(.+)",
            r"Re\s*[:\-]\s*(.+)",
            r"Regarding\s*[:\-]\s*(.+)",
        ],
        text,
    )

    # ── Items + Requirements from invoice rows or bullet sections ─
    invoice_items = _extract_invoice_line_items(text)
    items_raw, requirements_raw = _split_bullet_sections(text)

    # If the heuristic split didn't produce items, fall back to all bullets
    if not items_raw and requirements_raw:
        items_raw = requirements_raw
        requirements_raw = []
    elif not items_raw:
        items_raw = _extract_bullets(text)

    result["items"] = invoice_items or [{"name": b} for b in items_raw]
    result["requirements"] = requirements_raw

    # ── Deadline ─────────────────────────────────
    result["deadline"] = _first_match(
        [
            r"(?:by|before|no later than|deadline[:\s]+|quotation by)\s+([A-Za-z]+ \d{1,2},?\s*\d{4})",
            r"(?:by|before|no later than)\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        ],
        text,
    )

    # ── Body summary (first 400 chars of the body paragraph) ──
    body_match = re.search(r"Dear\s+.+?\n(.+)", text, re.DOTALL)
    if body_match:
        raw_body = body_match.group(1).strip()
        # Collapse whitespace
        raw_body = re.sub(r"\s+", " ", raw_body)
        result["body_summary"] = raw_body[:400]

    return result


def items_to_sourcing_lines(parsed: dict) -> str:
    """
    Convert extracted items list to the sourcing form line format:
        Item Name|Quantity|Unit|Notes
    Quantity/unit/notes are left blank as the agent fills those in during sourcing.
    """
    lines = []
    for item in parsed.get("items", []):
        name = (item.get("name") or item.get("description") or "").strip()
        if name:
            quantity = str(item.get("quantity") or "").strip()
            unit = str(item.get("unit") or "").strip()
            notes = str(item.get("notes") or "").strip()
            if item.get("unit_price") not in (None, ""):
                notes = (
                    notes + " | " if notes else ""
                ) + f"Source unit price: {item['unit_price']}"
            if item.get("total") not in (None, ""):
                notes = (
                    notes + " | " if notes else ""
                ) + f"Source total: {item['total']}"
            lines.append("|".join([name, quantity, unit, notes]).rstrip("|"))
    return "\n".join(lines)


def build_sourcing_notes(parsed: dict) -> str:
    """
    Build a clean pre-filled Notes block for the Sourcing form
    from the structured PI data.
    """
    parts = []

    if parsed.get("subject"):
        parts.append(f"Subject: {parsed['subject']}")

    parts.append(
        "Customer details are taken from the linked transaction entry, not from the uploaded document."
    )

    if parsed.get("deadline"):
        parts.append(f"Quotation Deadline: {parsed['deadline']}")

    if parsed.get("requirements"):
        parts.append("\nClient Requirements:")
        for req in parsed["requirements"]:
            parts.append(f"  • {req}")

    if parsed.get("body_summary"):
        parts.append(f"\nBrief: {parsed['body_summary']}")

    return "\n".join(parts)
