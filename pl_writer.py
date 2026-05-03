"""
Write COG values into the correct P&L Google Sheet.

Auth (in priority order):
  1. Streamlit secrets: [gcp_service_account] — used on Streamlit Cloud (team deployment)
  2. Local service account JSON file: service_account.json — for local use with service account
  3. OAuth2 credentials: credentials.json — fallback for local dev

To set up for Streamlit Cloud:
  - Create a GCP Service Account with Sheets API access
  - Share each P&L sheet with the service account email (Editor)
  - Add the service account JSON contents to Streamlit secrets as [gcp_service_account]
"""

import os
import json
import gspread
from datetime import date
from config import STORES, PL_COL_COG, PL_DATA_START_ROW

CREDENTIALS_FILE  = os.path.join(os.path.dirname(__file__), "credentials.json")
SERVICE_ACCT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")

_gc = None


def _get_client():
    global _gc
    if _gc:
        return _gc

    # 1. Streamlit Cloud secrets (team deployment)
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            _gc = gspread.service_account_from_dict(creds_dict)
            return _gc
    except Exception:
        pass

    # 2. Local service account JSON file
    if os.path.exists(SERVICE_ACCT_FILE):
        _gc = gspread.service_account(filename=SERVICE_ACCT_FILE)
        return _gc

    # 3. OAuth2 fallback (local dev)
    if os.path.exists(CREDENTIALS_FILE):
        token_file = os.path.join(os.path.dirname(__file__), "token.json")
        _gc = gspread.oauth(
            credentials_filename=CREDENTIALS_FILE,
            authorized_user_filename=token_file,
        )
        return _gc

    raise FileNotFoundError(
        "No Google credentials found.\n\n"
        "For local use: add service_account.json or credentials.json next to this script.\n"
        "For Streamlit Cloud: add [gcp_service_account] to your app secrets."
    )


def _month_tab_name(target_date):
    # Tabs are named APR, MAY, JUN etc. (3-letter abbreviation, uppercase)
    return target_date.strftime("%b").upper()


def _parse_sheet_date(val):
    from datetime import datetime
    # Includes DD.MM.YYYY format used in the P&L sheets
    formats = ["%d.%m.%Y", "%d.%m.%y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%y"]
    val = str(val).strip()
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _find_date_row(worksheet, target_date):
    col_a = worksheet.col_values(1)
    for i, val in enumerate(col_a):
        row_num = i + 1
        if row_num < PL_DATA_START_ROW:
            continue
        if not val:
            continue
        parsed = _parse_sheet_date(val)
        # Match by month and day only — P&L sheet may show a different year
        if parsed and parsed.month == target_date.month and parsed.day == target_date.day:
            return row_num
    return None


def write_cog_to_pl(invoice_data, store_key, dry_run=False):
    """
    Write daily COG totals into the P&L Google Sheet.
    Returns list of result dicts with status per date.
    """
    store = STORES.get(store_key)
    if not store:
        raise ValueError(f"Unknown store key: {store_key}")

    pl_sheet_id = store.get("pl_sheet_id")
    if not pl_sheet_id:
        raise ValueError(
            f"No P&L sheet ID configured for store '{store_key}'. "
            "Add it to config.py → STORES."
        )

    gc = _get_client()
    spreadsheet = gc.open_by_key(pl_sheet_id)
    results = []

    for target_date, cog_value in sorted(invoice_data["daily_totals"].items()):
        tab_name = _month_tab_name(target_date)

        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            results.append({
                "date": target_date, "cog": cog_value, "row": None,
                "tab": tab_name,
                "status": f"ERROR — tab '{tab_name}' not found in sheet",
            })
            continue

        row_num = _find_date_row(worksheet, target_date)

        if row_num is None:
            results.append({
                "date": target_date, "cog": cog_value, "row": None,
                "tab": tab_name,
                "status": f"ERROR — date {target_date} not found in {tab_name} tab",
            })
            continue

        cog_col = PL_COL_COG + 1  # 0-indexed → 1-indexed

        if dry_run:
            results.append({
                "date": target_date, "cog": cog_value, "row": row_num,
                "tab": tab_name,
                "status": f"DRY RUN — would write ${cog_value:.2f} to {tab_name} row {row_num}",
            })
        else:
            worksheet.update_cell(row_num, cog_col, round(cog_value, 2))
            results.append({
                "date": target_date, "cog": cog_value, "row": row_num,
                "tab": tab_name,
                "status": f"OK — wrote ${cog_value:.2f} to {tab_name} row {row_num}",
            })

    return results
