#!/usr/bin/env python3
"""
Generate order report JSON data from B0961005 daily order report xlsx.
Run after downloading the latest order report from MMS.
"""
import openpyxl, json, sys
from collections import defaultdict

def process_order_report(xlsx_path, output_json_path):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.active

    gmv_daily = defaultdict(float)
    gmv_hourly = defaultdict(lambda: defaultdict(float))
    gmv_sku_daily = defaultdict(lambda: defaultdict(float))
    qty_sku_daily = defaultdict(lambda: defaultdict(float))
    gmv_brand_daily = defaultdict(lambda: defaultdict(float))
    order_count_daily = defaultdict(int)
    sku_names = {}
    brand_names = {}
    sku_brand_map = {}

    for row in ws.iter_rows(min_row=6, values_only=True):
        order_date = row[6]   # G: Order Date
        order_time = row[7]   # H: Order Time
        sku_id_raw = row[17]  # R: SKU ID
        brand_cn = row[19]    # T: SKU brand (Chinese)
        qty = row[23]         # X: Qty
        unit_price = row[24]  # Y: Unit Price
        discount = row[25]    # Z: Discount
        gmv = row[26]         # AA: Total GMV

        if not order_date or not sku_id_raw:
            continue

        date_str = str(order_date)[:10]
        if not date_str:
            continue

        # Parse hour from time
        hour = 0
        if order_time:
            time_str = str(order_time)
            if ':' in time_str:
                try:
                    hour = int(time_str.split(':')[0])
                except:
                    hour = 0

        # Full SKU ID format: B0961005_S_{R_value}
        full_sku = f'B0961005_S_{sku_id_raw}'

        # GMV calculation
        try:
            qty_val = float(qty) if qty else 0
            price_val = float(unit_price) if unit_price else 0
            disc_val = float(discount) if discount else 0
            gmv_val = float(gmv) if gmv else (qty_val * price_val - disc_val)
        except:
            gmv_val = 0

        # Aggregate
        gmv_daily[date_str] += gmv_val
        gmv_hourly[date_str][hour] += gmv_val
        gmv_sku_daily[full_sku][date_str] += gmv_val
        qty_sku_daily[full_sku][date_str] += qty_val
        brand = str(brand_cn) if brand_cn else 'Unknown'
        gmv_brand_daily[brand][date_str] += gmv_val
        order_count_daily[date_str] += 1
        sku_names[full_sku] = row[21]  # V: SKU Name Chinese
        brand_names[brand] = brand
        sku_brand_map[full_sku] = brand  # SKU -> Brand mapping

    output = {
        'gmv_daily': dict(gmv_daily),
        'gmv_hourly': {k: dict(v) for k, v in gmv_hourly.items()},
        'gmv_sku_daily': {k: dict(v) for k, v in gmv_sku_daily.items()},
        'qty_sku_daily': {k: dict(v) for k, v in qty_sku_daily.items()},
        'gmv_brand_daily': {k: dict(v) for k, v in gmv_brand_daily.items()},
        'order_count_daily': dict(order_count_daily),
        'sku_names': sku_names,
        'sku_brand_map': sku_brand_map,
        'brand_names': dict(brand_names),
        'generated': str(sys.argv[1]) if len(sys.argv) > 1 else 'unknown'
    }

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Processed {sum(order_count_daily.values())} orders, {len(sku_names)} SKUs, {len(brand_names)} brands")
    print(f"Total GMV: ${sum(gmv_daily.values()):.2f}")
    print(f"Output: {output_json_path}")

if __name__ == '__main__':
    xlsx = sys.argv[1] if len(sys.argv) > 1 else 'order_report_latest.xlsx'
    out = sys.argv[2] if len(sys.argv) > 2 else 'order_data.json'
    process_order_report(xlsx, out)
