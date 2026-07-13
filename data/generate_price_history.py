#!/usr/bin/env python3
"""
B0961005 Daily Price History Generator
Reads the latest Exchange Jerry inventory CSV, extracts RSP/PSP for each SKU,
and appends a new daily snapshot to the price history JSON file.

Format: { "SKU_CODE": [{"date": "2026-06-14", "rsp": 49.9, "psp": 34.9}, ...], ... }

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

def get_latest_csv():
    """Get the most recent non-empty CSV from cron output dir."""
    files = sorted(CRON_OUTPUT_DIR.glob("inventory_report_*.csv"), key=lambda f: f.stat().st_mtime)
    if not files:
        return None
    valid = [f for f in files if f.stat().st_size > 100]
    if not valid:
        return None
    return valid[-1]

def parse_inventory_csv(csv_path):
    """Parse the Exchange Jerry inventory CSV and return {sku: {rsp, psp, name}} dict."""
    skus = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    header = None
    data_start = 0
    for i, row in enumerate(rows):
        if row and len(row) >= 6 and row[0] == "Merchant ID" and "Merchant SKU ID" in row:
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
    """Load existing price history (SKU-centric format)."""
    if PRICE_HISTORY_FILE.exists():
        with open(PRICE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    """Save price history to JSON file."""
    PRICE_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRICE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(history)} SKUs to {PRICE_HISTORY_FILE}")

def append_daily_snapshot(history, csv_path):
    """Append today's snapshot to the SKU-centric history."""
    today = date.today().isoformat()
    csv_skus = parse_inventory_csv(csv_path)

    if not csv_skus:
        print("WARNING: No SKUs found in CSV!")
        return history

    # Remove any stray date-key entries (from older format)
    date_keys = [k for k in history if k.startswith("20") and len(k) == 10 and k[4] == "-"]
    for dk in date_keys:
        del history[dk]

    tracked = 0
    new_skus = 0
    for sku, data in csv_skus.items():
        entry = {"date": today, "rsp": data["rsp"], "psp": data["psp"]}
        if sku in history:
            tracked += 1
            existing_dates = {e["date"] for e in history[sku]}
            if today not in existing_dates:
                history[sku].append(entry)
        else:
            new_skus += 1
            history[sku] = [entry]

    print(f"Added snapshot for {today}: {tracked} existing SKUs updated, {new_skus} new SKUs added")
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
    all_dates = set()
    max_dates = 0
    for sku, entries in history.items():
        dates_set = {e["date"] for e in entries}
        all_dates.update(dates_set)
        if len(dates_set) > max_dates:
            max_dates = len(dates_set)

    sorted_dates = sorted(all_dates)
    print(f"\nHistory summary:")
    print(f"  Total SKUs tracked: {len(history)}")
    print(f"  Total unique dates: {len(sorted_dates)}")
    print(f"  Max snapshots per SKU: {max_dates}")
    print(f"  Date range: {sorted_dates[0]} to {sorted_dates[-1]}" if sorted_dates else "  No dates")

if __name__ == "__main__":
    main()
