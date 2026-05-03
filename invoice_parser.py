"""
Parse DayOne (and HST) invoice XLSX files into structured data.
"""
import openpyxl
from collections import defaultdict
from datetime import datetime, date
from config import DAYONE_COLS, STORE_DETECT


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, (datetime,)):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _detect_store(store_col_value):
    if not store_col_value:
        return "unknown"
    val = str(store_col_value).lower()
    for fragment, key in STORE_DETECT.items():
        if fragment in val:
            return key
    return "unknown"


def _normalize_sku(sku):
    """Strip variant suffix from SKU for base matching. e.g. FRUGAZ-0673-19 -> FRUGAZ-0673"""
    if not sku:
        return None
    sku = str(sku).strip()
    parts = sku.split("-")
    # DayOne ERP SKUs: FRUGAZ-XXXX or DSHD5-XM838XXX (no trailing variant number)
    # Variant SKUs: FRUGAZ-XXXX-19 (has trailing variant)
    # Keep first two segments as base key
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return sku


def load_invoice(filepath):
    """
    Load an invoice XLSX and return a list of row dicts plus metadata.

    Returns:
        {
            "store": str,
            "rows": [ {order_id, order_name, paid_at, customer, country,
                       variant_sku, erp_sku, quantity, unit_price, discount,
                       in_total, title, is_refund} ],
            "daily_totals": { date: float },
            "refund_rows": [ ... ],
            "grand_total": float,
        }
    """
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active

    raw_rows = list(ws.iter_rows(values_only=True))
    if not raw_rows:
        raise ValueError("Invoice file is empty.")

    # Build column index from header row
    header = [str(h).strip() if h else "" for h in raw_rows[0]]
    col = {name: header.index(name) for name in header if name}

    def get(row, field_key):
        col_name = DAYONE_COLS.get(field_key)
        if col_name and col_name in col:
            return row[col[col_name]]
        return None

    rows = []
    store_key = "unknown"

    for raw in raw_rows[1:]:
        if all(v is None for v in raw):
            continue

        paid_at = _parse_date(get(raw, "paid_at"))

        def _to_float(val):
            if val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip()
            if s.startswith("="):
                return None  # formula cell — skip row
            try:
                return float(s.replace(",", ""))
            except ValueError:
                return None

        in_total = _to_float(get(raw, "in_total"))
        if in_total is None:
            continue  # skip formula/summary rows
        unit_price = _to_float(get(raw, "unit_price")) or 0.0
        discount = _to_float(get(raw, "discount")) or 0.0
        quantity = get(raw, "quantity") or 1

        if store_key == "unknown":
            store_key = _detect_store(get(raw, "store"))

        row = {
            "order_id": get(raw, "order_id"),
            "order_name": get(raw, "order_name"),
            "paid_at": paid_at,
            "customer": get(raw, "customer"),
            "country": get(raw, "country"),
            "variant_sku": get(raw, "variant_sku"),
            "erp_sku": get(raw, "erp_sku"),
            "erp_sku_base": _normalize_sku(get(raw, "erp_sku")),
            "variant_sku_base": _normalize_sku(get(raw, "variant_sku")),
            "quantity": quantity,
            "unit_price": unit_price,
            "discount": discount,
            "in_total": float(in_total),
            "title": get(raw, "title"),
            "is_refund": float(in_total) < 0,
        }
        rows.append(row)

    # Daily totals — sum In Total by date
    daily_totals = defaultdict(float)
    for r in rows:
        if r["paid_at"]:
            daily_totals[r["paid_at"]] += r["in_total"]

    refund_rows = [r for r in rows if r["is_refund"]]
    grand_total = sum(r["in_total"] for r in rows)

    return {
        "store": store_key,
        "rows": rows,
        "daily_totals": dict(sorted(daily_totals.items())),
        "refund_rows": refund_rows,
        "grand_total": grand_total,
    }
