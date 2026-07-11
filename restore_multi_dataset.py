#!/usr/bin/env python3
"""Restore multiDataset fields (SKU/Brand daily/monthly) from git and merge with current data."""
import json, re, subprocess

# Step 1: Get the original index.html from git before our changes
result = subprocess.run(
    ['git', 'show', '6de70c8:index.html'],
    capture_output=True, text=True, cwd='/home/snkwok/B0961005-Inventory-Dashboard'
)
orig_html = result.stdout

# Extract original salesTrendData
orig_match = re.search(r'const salesTrendData\s*=\s*(\{.*?\});', orig_html, re.DOTALL)
orig_data = json.loads(orig_match.group(1))

# Step 2: Read current (updated) index.html
with open('/home/snkwok/B0961005-Inventory-Dashboard/index.html', 'rb') as f:
    current_html = f.read().decode('utf-8')

current_match = re.search(r'const salesTrendData\s*=\s*(\{.*?\});', current_html, re.DOTALL)
current_data = json.loads(current_match.group(1))

# Step 3: Copy multiDataset fields from original
multi_fields = [
    'gmv_by_sku_daily', 'gmv_by_sku_monthly',
    'qty_by_sku_daily', 'qty_by_sku_monthly',
    'gmv_by_brand_daily', 'gmv_by_brand_monthly'
]

for field in multi_fields:
    if field in orig_data:
        current_data[field] = orig_data[field]
        print(f"Restored: {field} ({len(str(orig_data[field]))} chars)")
    else:
        print(f"WARNING: {field} not found in original data")

# Step 4: Write back
new_json = json.dumps(current_data, ensure_ascii=False, separators=(',', ':'))
new_html = current_html.replace(current_match.group(0), f'const salesTrendData = {new_json};')

with open('/home/snkwok/B0961005-Inventory-Dashboard/index.html', 'wb') as f:
    f.write(new_html.encode('utf-8'))

# Verify
with open('/home/snkwok/B0961005-Inventory-Dashboard/index.html', 'rb') as f:
    verify_html = f.read().decode('utf-8')

verify_match = re.search(r'const salesTrendData\s*=\s*(\{.*?\});', verify_html, re.DOTALL)
verify_data = json.loads(verify_match.group(1))

print("\n=== Verification ===")
for field in multi_fields:
    present = field in verify_data
    print(f"  {field}: {'✅ Present' if present else '❌ Missing'}")

# Check charts config
for key in ['gmvBySkuDaily', 'gmvBySkuMonthly', 'qtyBySkuDaily', 'qtyBySkuMonthly', 'gmvByBrandDaily', 'gmvByBrandMonthly']:
    config_match = re.search(rf"'{key}':\s*{{[^}}]+}}", verify_html)
    print(f"  {key} config: {'✅ Found' if config_match else '❌ Missing'}")
