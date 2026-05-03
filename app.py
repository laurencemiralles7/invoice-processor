import streamlit as st
import io
import os
from datetime import date
from pathlib import Path

from invoice_parser import load_invoice
from margin_checker import check_margins, _fetch_margin_sheet
from report_generator import generate_xlsx, generate_cassy_message, generate_pl_summary
from refund_checker import check_refunds
from config import STORES

st.set_page_config(
    page_title="Invoice Processor — Capital Brands",
    page_icon="📊",
    layout="wide",
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.big-metric { font-size: 2rem; font-weight: 700; }
.green  { color: #2e7d32; }
.orange { color: #e65100; }
.red    { color: #c62828; }
.grey   { color: #555; }
.tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin: 1px;
}
.tag-green  { background: #c8e6c9; color: #1b5e20; }
.tag-orange { background: #ffe0b2; color: #bf360c; }
.tag-red    { background: #ffcdd2; color: #b71c1c; }
.tag-grey   { background: #eeeeee; color: #333; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📊 Invoice Processor")
st.caption("Capital Brands B.V. / Mylea LLC — Finance Operations")
st.divider()

# ── File Upload ────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Drop the invoice file here",
    type=["xlsx"],
    help="DayOne or HST invoice export (.xlsx)",
)

if not uploaded:
    st.info("Upload an invoice file to get started.")
    st.stop()

# ── Parse ──────────────────────────────────────────────────────────────────────
with st.spinner("Reading invoice..."):
    invoice_bytes = uploaded.read()
    tmp_path = f"/tmp/{uploaded.name}"
    with open(tmp_path, "wb") as f:
        f.write(invoice_bytes)

    try:
        invoice_data = load_invoice(tmp_path)
    except Exception as e:
        st.error(f"Could not read invoice: {e}")
        st.stop()

store_key = invoice_data["store"]
store_config = STORES.get(store_key, {})
store_name = store_config.get("name", store_key.title())
margin_tab = store_config.get("margin_tab")

# ── Refund cross-check ─────────────────────────────────────────────────────────
with st.spinner("Cross-checking refund sheet..."):
    try:
        invoice_data = check_refunds(invoice_data)
        refund_check_ok = True
    except Exception as e:
        st.warning(f"Refund sheet check failed: {e}. Continuing without refund data.")
        invoice_data["refund_check_results"] = []
        invoice_data["refund_deductions"] = {}
        invoice_data["daily_totals_original"] = invoice_data["daily_totals"]
        refund_check_ok = False

# ── Summary bar ────────────────────────────────────────────────────────────────
cancelled_in_invoice = [
    r for r in invoice_data.get("refund_check_results", []) if r["in_invoice"]
]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Store", store_name)
col2.metric("Total rows", len(invoice_data["rows"]))
col3.metric("Cancelled (in invoice)", len(cancelled_in_invoice))
col4.metric("Grand total (adj.)", f"${invoice_data['grand_total']:,.2f}")

st.divider()

# ── Margin check ───────────────────────────────────────────────────────────────
if margin_tab:
    with st.spinner("Checking margins..."):
        try:
            invoice_data = check_margins(invoice_data, margin_tab)
        except Exception as e:
            st.warning(f"Margin check failed: {e}. Continuing without margin data.")

    color_counts = {}
    for r in invoice_data["rows"]:
        c = r.get("margin_color", "UNKNOWN")
        color_counts[c] = color_counts.get(c, 0) + 1

    st.subheader("Margin Summary")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("🟢 Green", color_counts.get("GREEN", 0))
    mc2.metric("🟠 Orange", color_counts.get("ORANGE", 0))
    mc3.metric("🔴 Red", color_counts.get("RED", 0))
    mc4.metric("⚠️ Not found", color_counts.get("NOT_FOUND", 0))
else:
    st.info(f"No margin sheet configured for store '{store_key}'.")

st.divider()

# ── Daily totals ───────────────────────────────────────────────────────────────
st.subheader("Daily Totals (COG)")

daily = invoice_data["daily_totals"]
daily_orig = invoice_data.get("daily_totals_original", daily)
deductions = invoice_data.get("refund_deductions", {})

dt_cols = st.columns(len(daily))
for i, (d, total) in enumerate(sorted(daily.items())):
    orig = daily_orig.get(d, total)
    delta = total - orig  # negative if deduction was applied
    if delta < 0:
        dt_cols[i].metric(str(d), f"${total:,.2f}", delta=f"${delta:,.2f} (cancelled deducted)", delta_color="off")
    else:
        dt_cols[i].metric(str(d), f"${total:,.2f}")

# ── Refund cross-check results ─────────────────────────────────────────────────
refund_results = invoice_data.get("refund_check_results", [])
if refund_results:
    st.divider()
    st.subheader("Refund Sheet Cross-Check")

    found_in_invoice = [r for r in refund_results if r["in_invoice"]]
    not_in_invoice   = [r for r in refund_results if not r["in_invoice"]]

    if found_in_invoice:
        st.error(
            f"**{len(found_in_invoice)} cancelled order(s) found in invoice** — "
            "deducted from COG totals above."
        )
        for r in found_in_invoice:
            st.markdown(
                f"- `{r['order_num']}` | {r['product']} | "
                f"Reason: **{r['reason']}** | "
                f"Deducted **${r['deducted']:.2f}** from {r['order_date']} COG"
            )
    else:
        st.success("No cancelled orders found in this invoice — supplier excluded them all correctly.")

    if not_in_invoice:
        with st.expander(f"{len(not_in_invoice)} refund sheet entries not in this invoice (already excluded)"):
            for r in not_in_invoice:
                st.markdown(f"- `{r['order_num']}` | {r['product']} | {r['reason']}")

st.divider()

# ── Issues ─────────────────────────────────────────────────────────────────────
issues_tab, rows_tab = st.tabs(["⚠️ Issues to Action", "📋 All Rows"])

with issues_tab:
    refunds = invoice_data.get("refund_rows", [])
    red_rows = [r for r in invoice_data["rows"] if r.get("margin_color") == "RED"]
    not_found = invoice_data.get("margin_not_found", [])

    if not refunds and not red_rows and not not_found:
        st.success("No issues found. All margins verified.")
    else:
        if refunds:
            st.markdown(f"**Refunds — {len(refunds)} orders (In Total = 0)**")
            for r in refunds:
                st.markdown(
                    f"- `{r['order_name']}` | {r['title']} | {r['customer']} | {r['country']}"
                )
            st.divider()

        if red_rows:
            st.markdown(f"**🔴 Red margin items — action required ({len(red_rows)} rows)**")
            seen = set()
            for r in red_rows:
                key = r.get("erp_sku") or r.get("title")
                if key not in seen:
                    seen.add(key)
                    roas = f"{r['be_roas']:.2f}" if r.get("be_roas") else "N/A"
                    cogs = f"{r['cogs_pct']:.1f}%" if r.get("cogs_pct") else "N/A"
                    st.markdown(
                        f"- `{r['erp_sku']}` **{r['title']}** — "
                        f"BE-ROAS: **{roas}** | COGs: **{cogs}**"
                    )
            st.divider()

        if not_found:
            st.markdown(f"**⚠️ Not in margin sheet — add manually ({len(not_found)} rows)**")
            seen = set()
            for r in not_found:
                key = r.get("erp_sku") or r.get("title")
                if key not in seen:
                    seen.add(key)
                    st.markdown(f"- `{r['erp_sku']}` {r['title']}")

with rows_tab:
    COLOR_LABEL = {
        "GREEN": "🟢", "ORANGE": "🟠", "RED": "🔴",
        "NOT_FOUND": "⚠️", "UNKNOWN": "❓",
    }
    rows_display = []
    for r in invoice_data["rows"]:
        color = r.get("margin_color", "")
        rows_display.append({
            "Order": r["order_name"],
            "Date": str(r["paid_at"]),
            "Customer": r["customer"],
            "Country": r["country"],
            "SKU": r["erp_sku"],
            "Title": r["title"],
            "Qty": r["quantity"],
            "Unit Price": r["unit_price"],
            "In Total": r["in_total"],
            "Margin": COLOR_LABEL.get(color, color),
            "BE-ROAS": round(r["be_roas"], 2) if r.get("be_roas") else "",
            "COGs%": f"{r['cogs_pct']:.1f}%" if r.get("cogs_pct") else "",
        })
    st.dataframe(rows_display, use_container_width=True, height=400)

st.divider()

# ── Cassy message ──────────────────────────────────────────────────────────────
st.subheader("Cassy Message")
cassy_msg = generate_cassy_message(invoice_data, store_name, uploaded.name)
st.code(cassy_msg, language=None)
st.caption("Copy the message above and paste it into the correct Slack channel.")

st.divider()

# ── Downloads ──────────────────────────────────────────────────────────────────
st.subheader("Download Processed Invoice")

xlsx_buffer = io.BytesIO()
generate_xlsx(invoice_data, xlsx_buffer)
xlsx_buffer.seek(0)
stem = Path(uploaded.name).stem
st.download_button(
    label="⬇️ Download processed invoice (.xlsx)",
    data=xlsx_buffer,
    file_name=f"{stem}_processed.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

# ── P&L Write ──────────────────────────────────────────────────────────────────
st.subheader("Write to P&L Google Sheet")

pl_sheet_id = store_config.get("pl_sheet_id")

if not pl_sheet_id:
    st.warning(
        f"No P&L sheet configured for **{store_name}**. "
        "Add the sheet ID to `config.py` to enable this."
    )
else:
    st.markdown(
        "COG is calculated from the invoice. "
        "Fill in **Revenue, Adspend Google, and Mediabuying** for each date below."
    )
    st.caption("Leave a field blank to skip writing that value for that date.")

    # ── Manual inputs per date ──────────────────────────────────────────────
    manual_inputs = {}
    header_cols = st.columns([2, 2, 2, 2, 2])
    header_cols[0].markdown("**Date**")
    header_cols[1].markdown("**COG** *(from invoice)*")
    header_cols[2].markdown("**Revenue**")
    header_cols[3].markdown("**Adspend Google**")
    header_cols[4].markdown("**Mediabuying**")

    for d, cog in sorted(daily.items()):
        row_cols = st.columns([2, 2, 2, 2, 2])
        row_cols[0].markdown(f"**{d}**")
        row_cols[1].markdown(f"`${cog:,.2f}`")
        rev_str   = row_cols[2].text_input("", placeholder="e.g. 2769.95", key=f"rev_{d}",   label_visibility="collapsed")
        ads_str   = row_cols[3].text_input("", placeholder="e.g. 1500.00", key=f"ads_{d}",   label_visibility="collapsed")
        media_str = row_cols[4].text_input("", placeholder="e.g. 200.00",  key=f"media_{d}", label_visibility="collapsed")

        def _parse(s):
            try:
                v = float(s.replace(",", ".").strip())
                return v if v > 0 else None
            except (ValueError, AttributeError):
                return None

        manual_inputs[d] = {
            "revenue":     _parse(rev_str),
            "adspend":     _parse(ads_str),
            "mediabuying": _parse(media_str),
        }

    st.divider()

    def _run_pl_write(invoice_data, store_key, manual_inputs, dry_run):
        from pl_writer import write_pl_row
        mode = "DRY RUN" if dry_run else "LIVE"
        with st.spinner(f"Writing to P&L [{mode}]..."):
            try:
                results = write_pl_row(invoice_data, store_key, manual_inputs, dry_run=dry_run)
                for r in results:
                    status = r["status"]
                    if status.startswith("OK") or status.startswith("DRY"):
                        st.success(f"{r['date']} | {status}")
                    elif status.startswith("SKIPPED"):
                        st.warning(f"{r['date']} | {status}")
                    else:
                        st.error(f"{r['date']} | {status}")
            except FileNotFoundError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Error writing to sheet: {e}")

    col_dry, col_live = st.columns([1, 1])
    with col_dry:
        if st.button("🔍 Dry Run (preview only)", use_container_width=True):
            _run_pl_write(invoice_data, store_key, manual_inputs, dry_run=True)
    with col_live:
        if st.button("✅ Write to P&L Sheet", type="primary", use_container_width=True):
            _run_pl_write(invoice_data, store_key, manual_inputs, dry_run=False)
