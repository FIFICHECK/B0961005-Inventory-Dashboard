#!/usr/bin/env python3
"""Update the inline salesTrendData in index.html with July 10 & 11 data."""
import re, json, copy

HTML_PATH = '/home/snkwok/B0961005-Inventory-Dashboard/index.html'

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# Find the const salesTrendData = {...} block
pattern = r'(const salesTrendData\s*=\s*)(\{.*?\});'
match = re.search(pattern, html, re.DOTALL)
if not match:
    print("ERROR: Could not find salesTrendData in HTML")
    exit(1)

prefix = match.group(1)
data_json_str = match.group(2)

# Parse the JSON
data = json.loads(data_json_str)

# 1. Update gmv_by_date - add July 11 and July 10 at front
data['gmv_by_date']['labels'].insert(0, '2026-07-11')
data['gmv_by_date']['labels'].insert(1, '2026-07-10')
data['gmv_by_date']['data'].insert(0, 134418.82)
data['gmv_by_date']['data'].insert(1, 63754.80)

# 2. Update gmv_by_month - July total
old_july_gmv = data['gmv_by_month']['data'][0]
new_july_gmv = round(old_july_gmv + 63754.80 + 134418.82, 2)
data['gmv_by_month']['data'][0] = new_july_gmv

# 3. Update gmv_by_hour - recalculate including July 10 & 11
# Current hourly data includes all dates. Need to add July 10 & 11.
jul10_hourly = [4337.1, 1087.7, 580.5, 139.0, 346.0, 266.8, 1547.7, 1251.6, 
                2187.9, 1914.2, 3907.0, 4672.0, 1966.8, 2430.1, 3192.8, 4308.5,
                3682.4, 2571.5, 2814.0, 3810.3, 3193.9, 2460.2, 5726.0, 5360.6]
jul11_hourly = [5734.5, 6314.37, 3554.5, 148.9, 440.6, 989.0, 2145.4, 2658.7,
                4607.1, 7514.1, 9784.25, 17023.0, 11020.9, 9703.2, 8768.8, 19303.1,
                11430.3, 9970.5, 5220.6, 0, 0, 0, 0, 0]

for h in range(24):
    data['gmv_by_hour']['data'][h] = round(data['gmv_by_hour']['data'][h] + jul10_hourly[h] + jul11_hourly[h], 2)

# 4. Update gmv_by_day_of_week - add July 11 and 10 at front
data['gmv_by_day_of_week']['labels'].insert(0, '2026-07-11')
data['gmv_by_day_of_week']['labels'].insert(1, '2026-07-10')
data['gmv_by_day_of_week']['data'].insert(0, 134418.82)
data['gmv_by_day_of_week']['data'].insert(1, 63754.80)

# 5. Update gmv_by_date_hour - add July 10 & 11
jul10_hourly_data = [round(v, 2) for v in jul10_hourly]
jul11_hourly_data = [round(v, 2) for v in jul11_hourly]

new_gmv_by_date_hour = {}
new_gmv_by_date_hour['2026-07-11'] = jul11_hourly_data
new_gmv_by_date_hour['2026-07-10'] = jul10_hourly_data
# Copy existing data
for k, v in data['gmv_by_date_hour']['data'].items():
    new_gmv_by_date_hour[k] = v
data['gmv_by_date_hour']['data'] = new_gmv_by_date_hour
data['gmv_by_date_hour']['labels'].insert(0, '2026-07-11')
data['gmv_by_date_hour']['labels'].insert(1, '2026-07-10')

# 6. Update orders by date
data['orders_by_date']['labels'].insert(0, '2026-07-11')
data['orders_by_date']['labels'].insert(1, '2026-07-10')
data['orders_by_date']['data'].insert(0, 917)
data['orders_by_date']['data'].insert(1, 663)

# 7. Update orders by month - July
old_july_orders = data['orders_by_month']['data'][0]
data['orders_by_month']['data'][0] = old_july_orders + 917 + 663

# 8. Update available_months - ensure 2026-07 is first (it should already be)
# No change needed, just verify
if 'available_months' in data and '2026-07' not in data['available_months']:
    data['available_months'].insert(0, '2026-07')

# 9. Update summary
old_total_gmv = data['summary']['total_gmv']
old_total_orders = data['summary']['total_orders']
new_total_gmv = round(old_total_gmv + 63754.80 + 134418.82, 2)
new_total_orders = old_total_orders + 917 + 663
new_avg = round(new_total_gmv / new_total_orders, 2) if new_total_orders > 0 else 0

data['summary']['total_gmv'] = new_total_gmv
data['summary']['total_orders'] = new_total_orders
data['summary']['avg_order_value'] = new_avg
data['summary']['date_range'] = '2026-05-14 to 2026-07-11'

# Update this_month
new_this_month_gmv = round(data['summary']['this_month']['gmv'] + 63754.80 + 134418.82, 2)
new_this_month_orders = data['summary']['this_month']['orders'] + 917 + 663
new_this_month_avg = round(new_this_month_gmv / new_this_month_orders, 2) if new_this_month_orders > 0 else 0
data['summary']['this_month']['gmv'] = new_this_month_gmv
data['summary']['this_month']['orders'] = new_this_month_orders
data['summary']['this_month']['avg'] = new_this_month_avg

# Serialize back - compact JSON
new_json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

# Replace in HTML
old_full = match.group(0)
new_full = prefix + new_json_str + ';'
html = html.replace(old_full, new_full)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ Updated inline salesTrendData")
print(f"   GMV: ${old_total_gmv:,.2f} → ${new_total_gmv:,.2f}")
print(f"   Orders: {old_total_orders} → {new_total_orders}")
print(f"   July GMV: ${old_july_gmv:,.2f} → ${new_july_gmv:,.2f}")
print(f"   July Orders: {old_july_orders} → {old_july_orders + 917 + 663}")
print(f"   Date range: → 2026-05-14 to 2026-07-11")
