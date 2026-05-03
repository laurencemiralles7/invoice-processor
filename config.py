# Store configuration — add new stores here
# Each store maps to: its margin sheet tab, P&L sheet ID, and P&L sheet tab prefix

MARGIN_SHEET_ID = "1QC-3drquZtl_Qn0U3HOPjWOA9JMOnJtasDLv5KUf-3o"

STORES = {
    "frugaze": {
        "name": "Frugaze",
        "margin_tab": "FRUGAZE",
        "pl_sheet_id": "1PgZdavlPBss7O219hEUSSY9gPfrm5bGxbLhh96l95DI",
        "pl_tab_prefix": "",
        "currency": "USD",
    },
    "luuza": {
        "name": "Luuza",
        "margin_tab": "LUUZA",
        "pl_sheet_id": "1PgZdavlPBss7O219hEUSSY9gPfrm5bGxbLhh96l95DI",
        "pl_tab_prefix": "",
        "currency": "USD",
    },
    "zenvro": {
        "name": "Zenvro",
        "margin_tab": "DAYONE-ZENVRO",
        "pl_sheet_id": None,
        "pl_tab_prefix": "",
        "currency": "EUR",
    },
    "wohnish": {
        "name": "Wohnish",
        "margin_tab": "DAYONE-WOHNISH",
        "pl_sheet_id": None,
        "pl_tab_prefix": "",
        "currency": "EUR",
    },
}

# Store name fragments from invoice "Store" column → store key
STORE_DETECT = {
    "frugaze": "frugaze",
    "luuza": "luuza",
    "zenvro": "zenvro",
    "wohnish": "wohnish",
    "sunnerey": "sunnerey",
    "valerian": "valerian",
    "cozey": "cozey",
    "sklaire": "sklaire",
}

# Margin thresholds — Break Even ROAS = sell_price / (sell_price - buy_price)
# Below 2.0 = Green, 2.0–2.50 = Orange, above 2.50 = Red
MARGIN_GREEN_MAX = 2.0
MARGIN_ORANGE_MAX = 2.5

# P&L column positions (0-indexed from col A)
PL_COL_DATE = 0       # A
PL_COL_REVENUE = 1    # B
PL_COL_COG = 2        # C
PL_COL_ADSPEND = 3    # D
PL_COL_REFUNDS = 13   # N
PL_HEADER_ROW = 6     # row 6 (1-indexed) = headers
PL_DATA_START_ROW = 7 # row 7 (1-indexed) = first data row

# Invoice column names — DayOne format
DAYONE_COLS = {
    "order_id": "Order Id",
    "order_name": "Order Name",
    "store": "Store",
    "paid_at": "Paid At",
    "tracking": "Tracking Number",
    "customer": "Shipping Name",
    "country": "Country",
    "variant_sku": "Variant SKU",
    "erp_sku": "ERP SKU",
    "quantity": "Quantity",
    "unit_price": "Unit Price",
    "discount": "Discount",
    "in_total": "In Total",
    "title": "Title",
}

# Margin sheet column positions (0-indexed)
MARGIN_COL_TITLE = 1       # B
MARGIN_COL_VARIANT = 2     # C
MARGIN_COL_SKU = 3         # D
MARGIN_COL_COUNTRY = 4     # E
MARGIN_COL_PRICE = 5       # F — website price
MARGIN_COL_BUYING_USD = 6  # G — buying price $
MARGIN_COL_BUYING_EUR = 7  # H — buying price €
MARGIN_COL_BE_ROAS = 8     # I — break even ROAS
MARGIN_COL_MARGIN_USD = 9  # J — margin in $
MARGIN_COL_MARGIN_PCT = 10 # K — margin %
MARGIN_COL_COGS_PCT = 11   # L — COGs %
