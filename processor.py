#!/usr/bin/env python3
"""
Invoice Processor — Capital Brands / Mylea LLC
Usage:
    python3 processor.py <invoice_file.xlsx> [--dry-run] [--no-sheets]

Options:
    --dry-run     Show what would be written to P&L sheet without writing
    --no-sheets   Skip Google Sheets write entirely (output files only)

Outputs (saved next to the invoice file):
    <invoice>_processed.xlsx   — styled invoice with margin flags & daily subtotals
    <invoice>_cassy.txt        — ready-to-paste Slack message for Cassy
    <invoice>_pl_update.txt    — P&L update preview
"""

import sys
import os
import argparse
from pathlib import Path

from invoice_parser import load_invoice
from margin_checker import check_margins
from report_generator import generate_xlsx, generate_cassy_message, generate_pl_summary
from config import STORES


def main():
    parser = argparse.ArgumentParser(description="Process supplier invoice")
    parser.add_argument("invoice", help="Path to invoice XLSX file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview P&L updates without writing to Google Sheets")
    parser.add_argument("--no-sheets", action="store_true",
                        help="Skip Google Sheets entirely")
    args = parser.parse_args()

    invoice_path = Path(args.invoice).expanduser().resolve()
    if not invoice_path.exists():
        print(f"Error: file not found: {invoice_path}")
        sys.exit(1)

    out_dir = invoice_path.parent
    stem = invoice_path.stem

    print(f"\n{'='*60}")
    print(f"  Invoice Processor — {invoice_path.name}")
    print(f"{'='*60}\n")

    # ── Step 1: Parse invoice ─────────────────────────────────────
    print("[1/4] Parsing invoice...")
    invoice_data = load_invoice(str(invoice_path))
    store_key = invoice_data["store"]
    store_config = STORES.get(store_key, {})
    store_name = store_config.get("name", store_key.title())
    margin_tab = store_config.get("margin_tab")

    print(f"      Store detected: {store_name}")
    print(f"      Rows: {len(invoice_data['rows'])}")
    print(f"      Refunds: {len(invoice_data['refund_rows'])}")
    print(f"      Date range: {min(invoice_data['daily_totals'])} → {max(invoice_data['daily_totals'])}")
    print(f"      Grand total: ${invoice_data['grand_total']:.2f}")

    # ── Step 2: Check margins ─────────────────────────────────────
    if margin_tab:
        print(f"\n[2/4] Checking margins (tab: {margin_tab})...")
        invoice_data = check_margins(invoice_data, margin_tab)

        colors = {}
        for r in invoice_data["rows"]:
            c = r.get("margin_color", "UNKNOWN")
            colors[c] = colors.get(c, 0) + 1

        for color, count in sorted(colors.items()):
            symbol = {"GREEN": "🟢", "ORANGE": "🟠", "RED": "🔴",
                      "NOT_FOUND": "⚠️ ", "UNKNOWN": "❓"}.get(color, "  ")
            print(f"      {symbol} {color}: {count} items")

        if invoice_data.get("margin_not_found"):
            print(f"\n      ⚠️  {len(invoice_data['margin_not_found'])} products not in margin sheet — check Issues tab")
    else:
        print(f"\n[2/4] Skipping margin check (no margin tab configured for '{store_key}')")

    # ── Step 3: Generate output files ─────────────────────────────
    print(f"\n[3/4] Generating output files...")

    xlsx_out = out_dir / f"{stem}_processed.xlsx"
    generate_xlsx(invoice_data, str(xlsx_out))

    cassy_msg = generate_cassy_message(invoice_data, store_name, invoice_path.name)
    cassy_out = out_dir / f"{stem}_cassy.txt"
    cassy_out.write_text(cassy_msg, encoding="utf-8")
    print(f"      Saved: {cassy_out}")

    pl_preview = generate_pl_summary(invoice_data, store_name)
    pl_out = out_dir / f"{stem}_pl_update.txt"
    pl_out.write_text(pl_preview, encoding="utf-8")
    print(f"      Saved: {pl_out}")

    # ── Step 4: Write to P&L Google Sheet ────────────────────────
    if args.no_sheets:
        print(f"\n[4/4] Skipping Google Sheets write (--no-sheets)")
    else:
        pl_sheet_id = store_config.get("pl_sheet_id")
        if not pl_sheet_id:
            print(f"\n[4/4] Skipping Google Sheets write")
            print(f"      No P&L sheet ID configured for '{store_key}'.")
            print(f"      Add it to config.py → STORES['{store_key}']['pl_sheet_id']")
        else:
            from pl_writer import write_cog_to_pl
            mode = "DRY RUN" if args.dry_run else "LIVE"
            print(f"\n[4/4] Writing COG values to P&L sheet [{mode}]...")

            try:
                results = write_cog_to_pl(invoice_data, store_key, dry_run=args.dry_run)
                for r in results:
                    status_icon = "✓" if r["status"].startswith("OK") or r["status"].startswith("DRY") else "✗"
                    print(f"      {status_icon} {r['date']} → ${r['cog']:.2f}  |  {r['status']}")
            except FileNotFoundError as e:
                print(f"\n      ⚠️  Google Sheets auth not set up yet:")
                print(f"      {e}")
                print(f"\n      Run with --no-sheets to skip this step.")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Done.\n")
    print(f"  P&L daily totals:")
    for d, total in sorted(invoice_data["daily_totals"].items()):
        print(f"    {d}  ${total:.2f}")
    print(f"    {'─'*22}")
    print(f"    TOTAL        ${invoice_data['grand_total']:.2f}")
    print(f"\n  Cassy message → {cassy_out.name}")
    print(f"  Processed XLSX → {xlsx_out.name}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
