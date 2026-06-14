#!/usr/bin/env python3
"""
B0961005 Daily Price History Generator
Reads the latest Exchange Jerry inventory CSV, extracts RSP/PSP for each SKU,
and appends a new daily snapshot to the price history JSON file.

Usage: python3 generate_price_history.py
Cron:  Runs after the Exchange Jerry inventory download (e.g., 3AM, 11AM, 3PM, 6PM, 10PM)
"""

import csv
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Paths
REPO_DIR = Path("/tmp/B0961005-Inventory-Dashboard")
CRON_OUTPUT_DIR = Path.home() / ".hermes/cron/output/exchange-jerry-inventory"
PRICE_HISTORY_FILE = REPO_DIR / "data/price_history.json"

# The most recent CSV in cron output dir
def get_latest_csv():
    files = sorted(CRON_OUTPUT_DIR.glob("inventory_report_*.csv"), key=lambda f: f.stat().st_mtime)
    if not files:
        return None
    return files[-1]

def parse_inventory_csv(csv_path):
    """Parse the Exchange Jerry inventory CSV and return {sku: {rsp, psp, name}} dict."""
    skus = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Find the header row (row index 5 typically)
    header = None
    data_start = 0
    for i, row in enumerate(rows):
        if row and row[0] == "Merchant ID" and "Merchant SKU ID" in row:
            header = row
            data_start = i + 1
            break

    if header is None:
        print("ERROR: Could not find header row in CSV")
        return {}

    try:
        sku_idx = header.index("Merchant SKU ID")
        name_idx = header.index("SKU Name (Chi)")
        orig_idx = header.index("Original Price")
        disc_idx = header.index("Discount Price")
    except ValueError as e:
        print(f"ERROR: Missing column: {e}")
        return {}

    for row in rows[data_start:]:
        if not row or len(row) <= max(sku_idx, name_idx, orig_idx, disc_idx):
            continue
        sku = row[sku_idx].strip()
        if not sku:
            continue
        try:
            orig = float(row[orig_idx]) if row[orig_idx].strip() else 0.0
        except ValueError:
            orig = 0.0
        try:
            disc = float(row[disc_idx]) if row[disc_idx].strip() else 0.0
        except ValueError:
            disc = 0.0
        name = row[name_idx].strip()

        skus[sku] = {"rsp": orig, "psp": disc, "name": name}

    return skus

def load_history():
    """Load existing price history, or create empty structure."""
    if PRICE_HISTORY_FILE.exists():
        with open(PRICE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    """Save price history to JSON file."""
    PRICE_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRICE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(history)} days of history to {PRICE_HISTORY_FILE}")

def append_daily_snapshot(history, csv_path):
    """Append today's snapshot to history."""
    today = date.today().isoformat()  # "2026-06-14"
    skus = parse_inventory_csv(csv_path)

    if not skus:
        print("WARNING: No SKUs found in CSV!")
        return history

    history[today] = skus
    print(f"Added snapshot for {today} with {len(skus)} SKUs")
    return history

def main():
    csv_path = get_latest_csv()
    if not csv_path:
        print("ERROR: No inventory CSV found in", CRON_OUTPUT_DIR)
        sys.exit(1)

    print(f"Using CSV: {csv_path.name} (modified {datetime.fromtimestamp(csv_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})")

    history = load_history()
    history = append_daily_snapshot(history, csv_path)
    save_history(history)

    # Summary
    dates = sorted(history.keys())
    print(f"\nHistory summary: {len(dates)} days")
    if dates:
        print(f"  Earliest: {dates[0]}")
        print(f"  Latest:   {dates[-1]}")
        # Show first SKU from latest
        latest = history[dates[-1]]
        first_sku = next(iter(latest.values()))
        print(f"  Latest sample: RSP={first_sku['rsp']}, PSP={first_sku['psp']}")

if __name__ == "__main__":
    main()
