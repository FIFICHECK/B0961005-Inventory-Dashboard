#!/usr/bin/env python3
"""Fetch B0961005 inventory from MMS API and merge into dashboard inventory CSV.

Replaces the Exchange portal download (Part 1) — MMS API is daily/real-time.
Verified 2026-08-24: storeId 117310 = B0961005, 364 SKUs.

Usage: python3 fetch_mms_inventory.py <accessToken>
  token = `accessToken` cookie after MMS 2.0 login (merchant.shoalter.com)
  If the cookie read is blocked, capture the Authorization header via XHR interceptor
  on the inventory-report page (see mms-inventory-report skill).
"""
import csv, io, json, os, sys, subprocess, datetime, glob, shutil

TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('MMS_TOKEN', '')
if not TOKEN:
    print("!! usage: fetch_mms_inventory.py <accessToken>"); sys.exit(1)

# ---- B0961005 config ----
STORE_ID = 117310           # numeric store ID for B0961005 (captured from MMS UI XHR)
STORE_PREFIX = 'B0961005_S_'  # SKU prefix used in the dashboard CSV
INPUT_DIR = os.path.expanduser('~/.hermes/cron/output/exchange-jerry-inventory/')
# ------------------------------------------

API = 'https://merchant-inventory-api.shoalter.com/inventory/api/v2/product-inventory'
PAGE_SIZE = 1000

def fetch_page(n):
    body = json.dumps({"pageNumber": n, "pageSize": PAGE_SIZE,
                       "buCodeList": ["HKTV"], "storeId": [STORE_ID]})
    # Use curl (verified works; urllib gets 403 from this API's WAF)
    r = subprocess.run([
        'curl', '-s', '-m', '60', '-X', 'POST', API,
        '-H', 'Content-Type: application/json',
        '-H', 'Authorization: Bearer ' + TOKEN,
        '-H', 'Accept: application/json, text/plain, */*',
        '-H', 'Origin: https://merchant.shoalter.com',
        '-H', 'Referer: https://merchant.shoalter.com/',
        '-d', body,
    ], capture_output=True, text=True)
    return json.loads(r.stdout)

# ---- 1. Fetch all pages (pageSize max 1000) ----
rows, page, total = [], 1, None
while page <= 100:
    d = fetch_page(page)
    if d.get('code') != 'SUCCESS':
        print(f"!! API error page {page}: {d.get('response')}"); sys.exit(1)
    resp = d['response']
    total = resp.get('totalElement', 0)
    content = resp.get('content', [])
    rows.extend(content)
    if len(rows) >= total or not content:
        break
    page += 1
print(f"fetched {len(rows)} / {total} SKUs from MMS API (storeId {STORE_ID})")

# ---- 2. Build MMS lookup: normalized SKU -> live fields ----
mms = {}
for it in rows:
    sku = it.get('skuId', '')
    if not sku:
        continue
    bu = (it.get('buProductDetail') or [{}])[0]
    qty = int(it.get('merchantInventoryQty') or 0) + int(it.get('tplInventoryQty') or 0) \
        + int(it.get('consignmentInventoryQty') or 0)
    mms[sku] = {
        'stock': qty,
        'online': 'online' if str(bu.get('status', '')).upper() == 'ONLINE' else 'offline',
        'invisible': 'Y' if bu.get('isVisible') is False else 'N',
        'sku_name_en': it.get('skuNameEn', ''),
        'sku_name_ch': it.get('skuNameCh', ''),
    }
print(f"MMS lookup keys: {len(mms)}")

# ---- 3. Pick the latest Exchange CSV as baseline (preserve static fields) ----
csvs = sorted(glob.glob(os.path.join(INPUT_DIR, 'inventory_report_*.csv')))
if not csvs:
    print(f"!! no baseline CSV in {INPUT_DIR} — need an Exchange CSV first"); sys.exit(1)
# Skip corrupt downloads (body starts with 'File Not Exist')
base = None
for c in reversed(csvs):
    with open(c, encoding='utf-8-sig', errors='replace') as f:
        first = f.readline()
    if 'Stock Level Summary' in first or 'Merchant ID' in first:
        base = c
        break
if not base:
    print("!! all CSVs corrupt"); sys.exit(1)
print(f"baseline CSV: {os.path.basename(base)}")

with open(base, encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()
# data header is line index 5 (0-based); find the row with 'Merchant ID,Merchant Product ID'
hdr_idx = None
for i, l in enumerate(lines):
    if l.strip().startswith('Merchant ID,Merchant Product ID'):
        hdr_idx = i
        break
if hdr_idx is None:
    print("!! cannot find data header row in baseline CSV"); sys.exit(1)

# Parse header + data rows using csv module over the FULL block
# (single csv.reader pass handles quoted fields containing embedded newlines,
#  e.g. SKU names with '\n[BEST_BEFORE]' coming from MMS API skuNameEn)
all_rows = [r for r in csv.reader(io.StringIO(''.join(lines[hdr_idx:]))) if any((c or '').strip() for c in r)]
header = [h.strip() for h in all_rows[0]]
col_idx = {h: i for i, h in enumerate(header)}
print(f"baseline columns: {len(header)}")
data_rows = all_rows[1:]
print(f"baseline data rows: {len(data_rows)}")

# ---- 4. Merge MMS live fields ----
updated = missing = 0
for r in data_rows:
    if len(r) <= col_idx.get('Merchant SKU ID', 3):
        continue
    raw = r[col_idx['Merchant SKU ID']]
    sku = raw.replace(STORE_PREFIX, '')
    m = mms.get(sku)
    if m:
        r[col_idx['StockLevel']] = str(m['stock'])
        r[col_idx['Online Status']] = m['online']
        r[col_idx['Invisible']] = m['invisible']
        if m['sku_name_en'] and 'SKU Name' in col_idx:
            r[col_idx['SKU Name']] = m['sku_name_en']
        if m['sku_name_ch'] and 'SKU Name (Chi)' in col_idx:
            r[col_idx['SKU Name (Chi)']] = m['sku_name_ch']
        updated += 1
    else:
        missing += 1
print(f"merged: {updated} updated, {missing} SKUs not found in MMS response")

# ---- 5. Write output CSV (same format as Exchange download) ----
now = datetime.datetime.now()
out_name = f"inventory_report_{now.strftime('%Y%m%d_%H%M')}.csv"
out_path = os.path.join(INPUT_DIR, out_name)
with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
    # write metadata header lines (same as Exchange format)
    f.write("Stock Level Summary Report\n")
    f.write("Merchant ID,B0961005\n")
    f.write("Merchant Name,Hong Kong online Community pharmacy superstore\n")
    f.write(f"Date,{now.strftime('%Y/%m/%d')}\n")
    f.write("\n")
    w = csv.writer(f)
    w.writerow(header)
    for r in data_rows:
        w.writerow(r)
print(f"written {out_path} ({len(data_rows)} rows)")

# ---- 6. Copy into dashboard repo reports/ + data/ for consistency ----
REPO = os.path.expanduser('~/.hermes/cron/output/exchange-jerry-inventory-dashboard-repo')
shutil.copy2(out_path, os.path.join(REPO, 'reports', out_name))
print(f"copied to repo reports/{out_name}")
