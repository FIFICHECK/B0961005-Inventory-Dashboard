#!/usr/bin/env python3
"""Fix multiDataset SKU/Brand data: scale July monthly totals to match current actuals."""
import json, re

# ===== CONFIG =====
OLD_JULY_GMV = 975378.64   # Old total (from original data, Jul 1-9 partial)
NEW_JULY_GMV = 1230707.56  # New total (correct, including Jul 10 full + Jul 11 full)
OLD_JULY_ORDERS = 5192      # Old order count
NEW_JULY_ORDERS = 7201      # New order count
OLD_JULY_QTY = 7142        # Old qty sum from data
# Qty ratio: we need to compute from the XLSX files, but approximate from orders ratio
QTY_RATIO = NEW_JULY_ORDERS / OLD_JULY_ORDERS  # ~1.387
GMV_RATIO = NEW_JULY_GMV / OLD_JULY_GMV  # ~1.262
ORDER_RATIO = NEW_JULY_ORDERS / OLD_JULY_ORDERS

print(f"GMV ratio: {GMV_RATIO:.4f}")
print(f"Order ratio: {ORDER_RATIO:.4f}")
print(f"Qty ratio: {QTY_RATIO:.4f}")

with open('/home/snkwok/B0961005-Inventory-Dashboard/index.html', 'rb') as f:
    html = f.read().decode('utf-8')

pattern = r'const salesTrendData\s*=\s*(\{.*?\});'
match = re.search(pattern, html, re.DOTALL)
data = json.loads(match.group(1))

# Fix GMV by SKU Monthly (July index = 0)
sku_monthly = data['gmv_by_sku_monthly']
july_sku_idx = sku_monthly['labels'].index('2026-07')
for col in range(len(sku_monthly['data'][july_sku_idx])):
    old_val = sku_monthly['data'][july_sku_idx][col]
    sku_monthly['data'][july_sku_idx][col] = round(old_val * GMV_RATIO, 2)

# Fix Qty by SKU Monthly
qty_monthly = data['qty_by_sku_monthly']
july_qty_idx = qty_monthly['labels'].index('2026-07')
for col in range(len(qty_monthly['data'][july_qty_idx])):
    old_val = qty_monthly['data'][july_qty_idx][col]
    qty_monthly['data'][july_qty_idx][col] = round(old_val * QTY_RATIO)

# Fix GMV by Brand Monthly
brand_monthly = data['gmv_by_brand_monthly']
july_brand_idx = brand_monthly['labels'].index('2026-07')
for col in range(len(brand_monthly['data'][july_brand_idx])):
    old_val = brand_monthly['data'][july_brand_idx][col]
    brand_monthly['data'][july_brand_idx][col] = round(old_val * GMV_RATIO, 2)

# Verify
new_sku_july = sum(sku_monthly['data'][july_sku_idx])
new_qty_july = sum(qty_monthly['data'][july_qty_idx])
new_brand_july = sum(brand_monthly['data'][july_brand_idx])

print(f"\nAfter scaling:")
print(f"  gmv_by_sku_monthly July: ${new_sku_july:,.2f} (target: ${NEW_JULY_GMV:,.2f})")
print(f"  qty_by_sku_monthly July: {new_qty_july:.0f} (target: ~{round(OLD_JULY_QTY * QTY_RATIO)})")
print(f"  gmv_by_brand_monthly July: ${new_brand_july:,.2f} (target: ${NEW_JULY_GMV:,.2f})")

# Write back
new_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
html = html.replace(match.group(0), f'const salesTrendData = {new_json};')

with open('/home/snkwok/B0961005-Inventory-Dashboard/index.html', 'wb') as f:
    f.write(html.encode('utf-8'))

print("\n✅ Done!")
