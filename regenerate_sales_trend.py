#!/usr/bin/env python3
"""Regenerate sales_trend_data.js from order_data.json - COMPLETE version"""
import json
from datetime import datetime

with open('data/order_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

gmv_daily = d['gmv_daily']
gmv_hourly = d['gmv_hourly']
qty_sku_daily = d['qty_sku_daily']
gmv_sku_daily = d['gmv_sku_daily']
gmv_brand_daily = d['gmv_brand_daily']
sku_names = d['sku_names']
sku_brand_map = d['sku_brand_map']
order_count = d['order_count_daily']

dates = sorted(gmv_daily.keys())
labels_date = dates[::-1]  # newest first

# GMV by date
data_date = [round(gmv_daily.get(d, 0), 2) for d in labels_date]
gmv_monthly_total = round(sum(gmv_daily.values()), 2)

# GMV by hour
all_hours_labels = [f"{h:02d}" for h in range(24)]
gmv_hour = [round(sum(gmv_hourly.get(d, {}).get(f"{h:02d}", 0) for d in dates), 2) for h in range(24)]

# Day of week
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_labels = []
dow_data = []
for ds in labels_date:
    dt = datetime.strptime(ds, '%Y-%m-%d')
    dow_labels.append(f"{DAY_NAMES[dt.weekday()]} ({ds})")
    dow_data.append(round(gmv_daily.get(ds, 0), 2))

# Order count
order_data = [order_count.get(d, 0) for d in labels_date]

# Top 50 SKUs (daily)
sku_totals = {sku: sum(dates_dict.values()) for sku, dates_dict in gmv_sku_daily.items()}
top_skus = sorted(sku_totals, key=lambda x: -sku_totals[x])[:50]
labels_sku = labels_date
sku_data = [[round(gmv_sku_daily.get(sku, {}).get(d, 0), 2) for d in labels_sku] for sku in top_skus]
qty_sku_data_arr = [[round(qty_sku_daily.get(sku, {}).get(d, 0), 2) for d in labels_sku] for sku in top_skus]

# GMV by Brand daily (top 20 brands)
brand_totals = {brand: sum(dates_dict.values()) for brand, dates_dict in gmv_brand_daily.items()}
top_brands = sorted(brand_totals, key=lambda x: -brand_totals[x])[:20]
brand_data = [[round(gmv_brand_daily.get(brand, {}).get(d, 0), 2) for d in labels_date] for brand in top_brands]

# GMV by SKU monthly (aggregate daily -> monthly)
gmv_sku_monthly = {}
qty_sku_monthly = {}
for sku, dates_dict in gmv_sku_daily.items():
    for date_str, gmv_val in dates_dict.items():
        month = date_str[:7]  # "2026-06"
        if month not in gmv_sku_monthly:
            gmv_sku_monthly[month] = {}
            qty_sku_monthly[month] = {}
        gmv_sku_monthly[month][sku] = gmv_sku_monthly[month].get(sku, 0) + gmv_val
        qty_sku_monthly[month][sku] = qty_sku_monthly[month].get(sku, 0) + qty_sku_daily.get(sku, {}).get(date_str, 0)

# GMV by Brand monthly
gmv_brand_monthly = {}
for brand, dates_dict in gmv_brand_daily.items():
    for date_str, gmv_val in dates_dict.items():
        month = date_str[:7]
        if month not in gmv_brand_monthly:
            gmv_brand_monthly[month] = {}
        gmv_brand_monthly[month][brand] = gmv_brand_monthly[month].get(brand, 0) + gmv_val

# Monthly data arrays for charts
month_labels = sorted(gmv_sku_monthly.keys())  # e.g. ["2026-06"]
sku_monthly_data = [[round(gmv_sku_monthly.get(m, {}).get(sku, 0), 2) for m in month_labels] for sku in top_skus]
qty_sku_monthly_data = [[round(qty_sku_monthly.get(m, {}).get(sku, 0), 2) for m in month_labels] for sku in top_skus]
brand_monthly_data = [[round(gmv_brand_monthly.get(m, {}).get(brand, 0), 2) for m in month_labels] for brand in top_brands]

# Summary
total_gmv = round(sum(gmv_daily.values()), 2)
total_orders = sum(order_count.values())
avg_order_value = round(total_gmv / total_orders, 2) if total_orders > 0 else 0

# GMV by date-hour
gmv_by_date_hour = {}
for ds in labels_date:
    gmv_by_date_hour[ds] = [round(gmv_hourly.get(ds, {}).get(f"{h:02d}", 0), 2) for h in range(24)]

print(f"Total GMV: ${total_gmv:,.2f}")
print(f"Total Orders: {total_orders}")
print(f"Dates: {labels_date}")
print(f"GMV by date: {data_date}")
print(f"Month labels: {month_labels}")
print(f"Top SKUs: {len(top_skus)}")
print(f"Top Brands: {len(top_brands)}")

chart_data = {
    "gmv_by_date": {"labels": labels_date, "data": data_date},
    "gmv_by_month": {"labels": month_labels, "data": [gmv_monthly_total]},
    "gmv_by_hour": {"labels": all_hours_labels, "data": gmv_hour},
    "gmv_by_day_of_week": {"labels": dow_labels, "data": dow_data},
    "gmv_by_date_hour": {"labels": labels_date, "hours": all_hours_labels, "data": gmv_by_date_hour},
    "orders_by_date": {"labels": labels_date, "data": order_data},
    # Daily SKU charts
    "gmv_by_sku_daily": {"labels": labels_sku, "skus": top_skus, "data": sku_data},
    "qty_by_sku_daily": {"labels": labels_sku, "skus": top_skus, "data": qty_sku_data_arr},
    # Monthly SKU charts
    "gmv_by_sku_monthly": {"labels": month_labels, "skus": top_skus, "data": sku_monthly_data},
    "qty_by_sku_monthly": {"labels": month_labels, "skus": top_skus, "data": qty_sku_monthly_data},
    # Daily Brand charts
    "gmv_by_brand_daily": {"labels": labels_date, "brands": top_brands, "data": brand_data},
    # Monthly Brand charts
    "gmv_by_brand_monthly": {"labels": month_labels, "brands": top_brands, "data": brand_monthly_data},
    "sku_name_map": sku_names,
    "sku_brand_map": sku_brand_map,
    "summary": {
        "total_gmv": total_gmv,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "date_range": f"{labels_date[-1]} to {labels_date[0]}"
    }
}

js_content = f"""// Auto-generated sales trend data
// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// Source: order_data.json (merged from all 23:59 daily order reports)

const salesTrendData = {json.dumps(chart_data, ensure_ascii=False, indent=2)};
"""

with open('data/sales_trend_data.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

print(f"\nGenerated: data/sales_trend_data.js ({len(js_content)} bytes)")
print(f"Keys in chart_data: {list(chart_data.keys())}")