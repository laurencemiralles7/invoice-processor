#!/bin/bash
# Double-click this file to run the invoice processor.
# It will find the most recent invoice in your Downloads folder automatically.

cd "$(dirname "$0")"

echo "================================================"
echo "  Invoice Processor — Capital Brands / Mylea"
echo "================================================"
echo ""

# Find the most recent .xlsx file in Downloads that looks like an invoice
INVOICE=$(ls -t ~/Downloads/*.xlsx 2>/dev/null | head -1)

if [ -z "$INVOICE" ]; then
    echo "No .xlsx files found in your Downloads folder."
    echo "Please download the invoice file and try again."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

echo "Found invoice: $(basename "$INVOICE")"
echo ""
read -p "Process this file? (y/n): " CONFIRM

if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo ""
    echo "Cancelled. Move the correct invoice to your Downloads folder and try again."
    read -p "Press Enter to close..."
    exit 0
fi

echo ""
python3 processor.py "$INVOICE"

echo ""
read -p "Done. Press Enter to close..."
