"""
Cross-check invoice orders against the central refund sheet.

Logic:
- Fetch the refund sheet (publicly accessible CSV export)
- For each cancelled/refunded order in the sheet, check if its Order # appears
  in the uploaded invoice's Order Name column
- If found in both → supplier double-counted it; deduct its In Total from that
  day's COG (using the order date from the invoice, not the refund date)
- If not found in invoice → supplier already excluded it; nothing to do

Returns an updated invoice_data dict with:
  - daily_totals adjusted for deductions
  - refund_check_results: list of result dicts per refund sheet entry
"""

import csv
import io
import urllib.request
from config import REFUND_SHEET_ID, REFUND_SHEET_GID

# Column indices in refund sheet (0-based)
RCOL_ORDER   = 0   # A: Order #
RCOL_PRODUCT = 4   # E: Refunded product/s
RCOL_REASON  = 5   # F: Refund Reason
RCOL_AMOUNT  = 8   # I: Refund Amount
RCOL_DATE    = 9   # J: Date Applied

_refund_cache = None


def _fetch_refund_sheet():
    global _refund_cache
    if _refund_cache is not None:
        return _refund_cache

    url = (
        f"https://docs.google.com/spreadsheets/d/{REFUND_SHEET_ID}"
        f"/export?format=csv&gid={REFUND_SHEET_GID}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8")

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    entries = []
    for row in rows[1:]:  # skip header
        if not row or not row[RCOL_ORDER].strip():
            continue
        entries.append({
            "order_num": row[RCOL_ORDER].strip(),
            "product":   row[RCOL_PRODUCT].strip() if len(row) > RCOL_PRODUCT else "",
            "reason":    row[RCOL_REASON].strip()  if len(row) > RCOL_REASON  else "",
            "amount":    row[RCOL_AMOUNT].strip()  if len(row) > RCOL_AMOUNT  else "",
            "date":      row[RCOL_DATE].strip()    if len(row) > RCOL_DATE    else "",
        })

    _refund_cache = entries
    return entries


def check_refunds(invoice_data):
    """
    Cross-check invoice rows against the refund sheet.
    Mutates invoice_data in place:
      - Marks matched rows with is_cancelled = True
      - Adjusts daily_totals to deduct cancelled orders that the supplier included
      - Adds refund_check_results list to invoice_data

    Returns the updated invoice_data.
    """
    refund_entries = _fetch_refund_sheet()

    # Build lookup: order_num (uppercased) → refund entry
    refund_lookup = {e["order_num"].upper(): e for e in refund_entries}

    # Build lookup: order_name (uppercased) → invoice row
    invoice_by_order = {}
    for row in invoice_data["rows"]:
        name = row.get("order_name")
        if name:
            invoice_by_order[str(name).strip().upper()] = row

    results = []
    deductions = {}  # date → amount to deduct

    for entry in refund_entries:
        order_num_upper = entry["order_num"].upper()
        invoice_row = invoice_by_order.get(order_num_upper)

        if invoice_row:
            # Supplier included this cancelled order — mark and schedule deduction
            invoice_row["is_cancelled"] = True
            order_date = invoice_row.get("paid_at")
            amount = invoice_row["in_total"]
            if order_date:
                deductions[order_date] = deductions.get(order_date, 0.0) + amount

            results.append({
                "order_num":  entry["order_num"],
                "product":    entry["product"],
                "reason":     entry["reason"],
                "amount":     entry["amount"],
                "date":       entry["date"],
                "in_invoice": True,
                "deducted":   amount,
                "order_date": order_date,
                "note": (
                    f"Found in invoice — deducting ${amount:.2f} "
                    f"from {order_date} COG"
                ),
            })
        else:
            results.append({
                "order_num":  entry["order_num"],
                "product":    entry["product"],
                "reason":     entry["reason"],
                "amount":     entry["amount"],
                "date":       entry["date"],
                "in_invoice": False,
                "deducted":   0.0,
                "order_date": None,
                "note": "Not in invoice — supplier already excluded it",
            })

    # Apply deductions to daily_totals
    adjusted = dict(invoice_data["daily_totals"])
    for d, amount in deductions.items():
        if d in adjusted:
            adjusted[d] = round(adjusted[d] - amount, 2)

    invoice_data["daily_totals_original"] = dict(invoice_data["daily_totals"])
    invoice_data["daily_totals"] = adjusted
    invoice_data["grand_total"] = sum(adjusted.values())
    invoice_data["refund_check_results"] = results
    invoice_data["refund_deductions"] = deductions

    return invoice_data
