import os
import re
from datetime import date

SUPABASE_URL = os.environ.get("SUPABASE_URL")


def _sb():
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not SUPABASE_URL or not key:
        raise RuntimeError("Supabase not configured")
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], key)


# ---------------------------------------------------------------------------
# Client search
# ---------------------------------------------------------------------------

def search_clients(query: str) -> list:
    q = query.strip()
    if not q:
        return []
    sb = _sb()
    result = (
        sb.schema("sales")
        .from_("clients")
        .select("id, business_name, client_type, default_payment_mode, primary_contact_name, primary_contact_phone, gstin")
        .or_(f"business_name.ilike.%{q}%,primary_contact_phone.ilike.%{q}%,gstin.ilike.%{q}%")
        .eq("status", "active")
        .limit(10)
        .execute()
    )
    return result.data


# ---------------------------------------------------------------------------
# Address lookup
# ---------------------------------------------------------------------------

def get_client_addresses(client_id: int) -> list:
    sb = _sb()
    result = (
        sb.schema("sales")
        .from_("addresses")
        .select("*")
        .eq("client_id", client_id)
        .execute()
    )
    return result.data


def _addr_label(addr: dict) -> str:
    parts = []
    for key in ("label", "nickname", "address_type", "type"):
        if addr.get(key):
            parts.append(str(addr[key]))
            break
    for key in ("address_line1", "line1", "street", "line_1"):
        if addr.get(key):
            parts.append(str(addr[key]))
            break
    for key in ("city",):
        if addr.get(key):
            parts.append(str(addr[key]))
            break
    return ", ".join(parts) if parts else f"Address #{addr.get('id', '?')}"


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

def get_sku_price(sku_id: int, pack_format_id: int) -> float:
    from mock_data import MOCK_PRICES
    try:
        sb = _sb()
        today = date.today().isoformat()
        result = (
            sb.schema("sales")
            .from_("sku_prices")
            .select("price")
            .eq("sku_id", sku_id)
            .lte("effective_from", today)
            .or_(f"effective_to.is.null,effective_to.gte.{today}")
            .order("effective_from", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return float(result.data[0]["price"])
    except Exception:
        pass
    return MOCK_PRICES.get(pack_format_id, 0.0)


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------

def _next_order_no(sb) -> str:
    year = date.today().year
    result = (
        sb.schema("sales")
        .from_("orders")
        .select("order_no")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        last = result.data[0]["order_no"]  # e.g. "ORD-2026-000014"
        try:
            num = int(last.split("-")[2]) + 1
        except (IndexError, ValueError):
            num = 1
        return f"ORD-{year}-{num:06d}"
    return f"ORD-{year}-000001"


def create_order(
    client_id: int,
    payment_mode: str,
    lines: list,
    billing_address_id=None,
    shipping_address_id=None,
    notes: str = None,
    salesperson_id: int = 1,
    discount_pct: float = 0,
) -> dict:
    """
    lines: [{"sku_id": int, "sku_code": str, "flavour_name": str,
              "format_name": str, "quantity": int, "unit_price": float,
              "line_discount": float}]
    discount_pct: order-level discount percentage (e.g. 16.5 for 16.5%)
    Returns the created order dict with nested lines.
    """
    sb = _sb()

    subtotal = sum(l["quantity"] * l["unit_price"] for l in lines)
    line_discount = sum(l.get("line_discount", 0.0) * l["quantity"] for l in lines)
    order_discount = round(subtotal * float(discount_pct) / 100, 2) if discount_pct else 0
    discount = line_discount + order_discount
    total = subtotal - discount

    order_no = _next_order_no(sb)

    order_row = {
        "order_no": order_no,
        "client_id": client_id,
        "channel": "whatsapp",
        "order_type": "commercial",
        "payment_mode": payment_mode,
        "billing_address_id": billing_address_id,
        "shipping_address_id": shipping_address_id,
        "status": "draft",
        "salesperson_id": salesperson_id,
        "placed_by_client": False,
        "source": "whatsapp_ai",
        "is_urgent": False,
        "subtotal_amount": str(subtotal),
        "discount_amount": str(discount),
        "tax_amount": "0.00",
        "total_amount": str(total),
        "notes": notes,
    }

    order_res = sb.schema("sales").from_("orders").insert(order_row).execute()
    order_id = order_res.data[0]["id"]

    line_rows = []
    for l in lines:
        qty = l["quantity"]
        price = l["unit_price"]
        disc_per_unit = l.get("line_discount", 0.0)
        line_total = qty * price - disc_per_unit * qty
        line_rows.append({
            "order_id": order_id,
            "sku_id": l["sku_id"],
            "quantity": str(qty),
            "unit_price": str(price),
            "line_discount_amount": str(disc_per_unit * qty),
            "line_total": str(line_total),
            "status": "active",
        })

    sb.schema("sales").from_("order_lines").insert(line_rows).execute()

    return {
        **order_res.data[0],
        "subtotal": subtotal,
        "discount": discount,
        "discount_pct": float(discount_pct) if discount_pct else 0,
        "total": total,
        "lines": [
            {
                "sku_code": l["sku_code"],
                "flavour_name": l["flavour_name"],
                "format_name": l["format_name"],
                "quantity": l["quantity"],
                "unit_price": l["unit_price"],
                "line_total": l["quantity"] * l["unit_price"] - l.get("line_discount", 0.0) * l["quantity"],
            }
            for l in lines
        ],
    }
