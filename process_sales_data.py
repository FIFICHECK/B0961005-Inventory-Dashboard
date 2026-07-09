#!/usr/bin/env python3
"""
Process Order Report XLSX and generate sales trend chart data
for B0961005 Inventory Dashboard.

Charts generated:
1. GMV by date
2. Monthly GMV
3. GMV by hour
4. GMV by SKU daily
5. GMV by SKU monthly
6. Qty by SKU daily
7. Qty by SKU monthly
8. GMV by brand daily
9. GMV by brand monthly
10. GMV by day of week
"""

import pandas as pd
import json
from datetime import datetime

# Chinese day names (Monday=0, Sunday=6)
DAY_NAMES_CN = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
DAY_NAMES_EN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# File paths
INPUT_FILE = '/home/snkwok/B0961005-Inventory-Dashboard/reports/order_reports/ECOM-MMSNG_DAILY_ORDER_B0961005_20260708235959.xlsx'
OUTPUT_FILE = '/home/snkwok/B0961005-Inventory-Dashboard/data/sales_trend_data.js'

def process_order_report():
    """Process the order report xlsx and return processed dataframe."""
    # Read raw data
    df_raw = pd.read_excel(INPUT_FILE, header=None)
    
    # Row 4 has the headers, data starts at row 5
    data_start = 5
    headers = df_raw.iloc[4].tolist()
    
    # Extract relevant columns
    df = df_raw.iloc[data_start:].copy()
    df.columns = headers
    
    # Process and transform data
    df['Date'] = pd.to_datetime(df.iloc[:, 6])  # Order Date (G)
    df['Time'] = df.iloc[:, 7].astype(str)       # Order Time (H)
    df['Hour'] = df['Time'].str[:2]              # Extract hour
    df['SKU_ID'] = df.iloc[:, 17].astype(str)    # SKU ID (R)
    df['Brand'] = df.iloc[:, 19].astype(str)      # Brand Chinese (T)
    df['SKU_Name_CN'] = df.iloc[:, 21].astype(str) # SKU Name Chinese (V)
    df['Full_SKU'] = 'B0961005_S_' + df['SKU_ID'].str.replace('_', '_')
    df['Qty'] = pd.to_numeric(df.iloc[:, 23], errors='coerce').fillna(0).astype(int)  # Qty (X)
    df['UnitPrice'] = pd.to_numeric(df.iloc[:, 24], errors='coerce').fillna(0)  # UnitPrice (Y)
    df['Discount'] = pd.to_numeric(df.iloc[:, 25], errors='coerce').fillna(0)     # Discount (Z)
    df['GMV'] = pd.to_numeric(df.iloc[:, 26], errors='coerce').fillna(0)           # GMV (AA)
    
    # Add year-month for monthly aggregations
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    df['DateStr'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    return df

def generate_chart_data(df):
    """Generate all 9 chart datasets."""

    # Build SKU name mapping (Full_SKU -> SKU Name Chinese)
    sku_name_map = df.groupby('Full_SKU')['SKU_Name_CN'].first().to_dict()
    
    # Build SKU brand mapping (Full_SKU -> Brand Chinese)
    sku_brand_map = df.groupby('Full_SKU')['Brand'].first().to_dict()

    # Chart 1: GMV by Date
    gmv_by_date = df.groupby('DateStr')['GMV'].sum().reset_index()
    gmv_by_date = gmv_by_date.sort_values('DateStr')
    
    # Chart 2: Monthly GMV
    gmv_by_month = df.groupby('YearMonth')['GMV'].sum().reset_index()
    gmv_by_month = gmv_by_month.sort_values('YearMonth')
    
    # Chart 3: GMV by Hour (fill all 24 hours with 0 for missing ones)
    gmv_by_hour = df.groupby('Hour')['GMV'].sum().reset_index()
    gmv_by_hour = gmv_by_hour.sort_values('Hour')
    # Ensure all 24 hours are present
    hour_dict = dict(zip(gmv_by_hour['Hour'], gmv_by_hour['GMV']))
    all_hours = [f"{i:02d}" for i in range(24)]
    gmv_by_hour = {'labels': all_hours, 'data': [hour_dict.get(h, 0) for h in all_hours]}

    # Chart 10: GMV by Day of Week (labels: "Sunday (2026-06-21)" format)
    gmv_by_date_df = df.groupby('DateStr')['GMV'].sum().reset_index()
    gmv_by_date_df = gmv_by_date_df.sort_values('DateStr')
    dow_labels = []
    for date_str in gmv_by_date_df['DateStr']:
        dt = pd.to_datetime(date_str)
        day_idx = dt.weekday()
        dow_labels.append(f"{DAY_NAMES_EN[day_idx]} ({date_str})")
    gmv_by_day_of_week = {
        'labels': dow_labels,
        'data': gmv_by_date_df['GMV'].tolist()
    }
    
    # Chart 4: GMV by SKU Daily
    gmv_by_sku_daily = df.groupby(['DateStr', 'Full_SKU'])['GMV'].sum().reset_index()
    gmv_by_sku_daily_pivot = gmv_by_sku_daily.pivot(index='DateStr', columns='Full_SKU', values='GMV').fillna(0)
    
    # Chart 5: GMV by SKU Monthly
    gmv_by_sku_monthly = df.groupby(['YearMonth', 'Full_SKU'])['GMV'].sum().reset_index()
    gmv_by_sku_monthly_pivot = gmv_by_sku_monthly.pivot(index='YearMonth', columns='Full_SKU', values='GMV').fillna(0)
    
    # Chart 6: Qty by SKU Daily
    qty_by_sku_daily = df.groupby(['DateStr', 'Full_SKU'])['Qty'].sum().reset_index()
    qty_by_sku_daily_pivot = qty_by_sku_daily.pivot(index='DateStr', columns='Full_SKU', values='Qty').fillna(0)
    
    # Chart 7: Qty by SKU Monthly
    qty_by_sku_monthly = df.groupby(['YearMonth', 'Full_SKU'])['Qty'].sum().reset_index()
    qty_by_sku_monthly_pivot = qty_by_sku_monthly.pivot(index='YearMonth', columns='Full_SKU', values='Qty').fillna(0)
    
    # Chart 8: GMV by Brand Daily
    gmv_by_brand_daily = df.groupby(['DateStr', 'Brand'])['GMV'].sum().reset_index()
    gmv_by_brand_daily_pivot = gmv_by_brand_daily.pivot(index='DateStr', columns='Brand', values='GMV').fillna(0)
    
    # Chart 9: GMV by Brand Monthly
    gmv_by_brand_monthly = df.groupby(['YearMonth', 'Brand'])['GMV'].sum().reset_index()
    gmv_by_brand_monthly_pivot = gmv_by_brand_monthly.pivot(index='YearMonth', columns='Brand', values='GMV').fillna(0)
    
    return {
        'sku_name_map': sku_name_map,
        'sku_brand_map': sku_brand_map,
        'gmv_by_date': {
            'labels': gmv_by_date['DateStr'].tolist(),
            'data': gmv_by_date['GMV'].tolist()
        },
        'gmv_by_month': {
            'labels': gmv_by_month['YearMonth'].tolist(),
            'data': gmv_by_month['GMV'].tolist()
        },
        'gmv_by_hour': {
            'labels': gmv_by_hour['labels'],
            'data': gmv_by_hour['data']
        },
        'gmv_by_day_of_week': {
            'labels': gmv_by_day_of_week['labels'],
            'data': gmv_by_day_of_week['data']
        },
        'gmv_by_sku_daily': {
            'labels': gmv_by_sku_daily_pivot.index.tolist(),
            'skus': gmv_by_sku_daily_pivot.columns.tolist(),
            'data': gmv_by_sku_daily_pivot.values.tolist()
        },
        'gmv_by_sku_monthly': {
            'labels': gmv_by_sku_monthly_pivot.index.tolist(),
            'skus': gmv_by_sku_monthly_pivot.columns.tolist(),
            'data': gmv_by_sku_monthly_pivot.values.tolist()
        },
        'qty_by_sku_daily': {
            'labels': qty_by_sku_daily_pivot.index.tolist(),
            'skus': qty_by_sku_daily_pivot.columns.tolist(),
            'data': qty_by_sku_daily_pivot.values.tolist()
        },
        'qty_by_sku_monthly': {
            'labels': qty_by_sku_monthly_pivot.index.tolist(),
            'skus': qty_by_sku_monthly_pivot.columns.tolist(),
            'data': qty_by_sku_monthly_pivot.values.tolist()
        },
        'gmv_by_brand_daily': {
            'labels': gmv_by_brand_daily_pivot.index.tolist(),
            'brands': gmv_by_brand_daily_pivot.columns.tolist(),
            'data': gmv_by_brand_daily_pivot.values.tolist()
        },
        'gmv_by_brand_monthly': {
            'labels': gmv_by_brand_monthly_pivot.index.tolist(),
            'brands': gmv_by_brand_monthly_pivot.columns.tolist(),
            'data': gmv_by_brand_monthly_pivot.values.tolist()
        }
    }

def generate_js_file(chart_data, df, output_path):
    """Generate JavaScript file with chart data."""
    
    # Calculate summary statistics
    total_gmv = df['GMV'].sum()
    total_qty = int(df['Qty'].sum())
    total_orders = len(df)
    unique_skus = df['SKU_ID'].nunique()
    unique_brands = df['Brand'].nunique()
    date_range_min = df['DateStr'].min()
    date_range_max = df['DateStr'].max()
    avg_gmv = df['GMV'].mean() if len(df) > 0 else 0
    top_sku = df.groupby('Full_SKU')['GMV'].sum().idxmax() if len(df) > 0 else 'N/A'
    top_brand = df.groupby('Brand')['GMV'].sum().idxmax() if len(df) > 0 else 'N/A'
    
    chart_data_json = json.dumps(chart_data, indent=2, ensure_ascii=False)
    
    js_content = f'''// Auto-generated sales trend data
// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// Source: ECOM-MMSNG_DAILY_ORDER_B0961005_20260621180001.xlsx

const salesTrendData = {chart_data_json};

// Chart configurations
const chartConfigs = {{
    // Chart 1: GMV by Date (Line Chart)
    gmvByDate: {{
        type: 'line',
        label: '每日 GMV (Daily GMV)',
        xAxisLabel: '日期 (Date)',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_date',
        color: '#1e40af'
    }},
    // Chart 2: Monthly GMV (Bar Chart)
    gmvByMonth: {{
        type: 'bar',
        label: '每月 GMV (Monthly GMV)',
        xAxisLabel: '月份 (Month)',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_month',
        color: '#3b82f6'
    }},
    // Chart 3: GMV by Hour (Bar Chart)
    gmvByHour: {{
        type: 'bar',
        label: '每小時 GMV (Hourly GMV)',
        xAxisLabel: '小時 (Hour)',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_hour',
        color: '#16a34a'
    }},
    // Chart 10: GMV by Day of Week (Bar Chart)
    gmvByDayOfWeek: {{
        type: 'bar',
        label: 'GMV by Day of Week',
        xAxisLabel: 'Day of Week',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_day_of_week',
        color: '#7c3aed'
    }},
    // Chart 4: GMV by SKU Daily (Line Chart)
    gmvBySkuDaily: {{
        type: 'line',
        label: '各 SKU 每日 GMV (Daily GMV by SKU)',
        xAxisLabel: '日期 (Date)',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_sku_daily',
        multiDataset: true,
        colors: ['#1e40af', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#65a30d', '#f59e0b', '#6366f1']
    }},
    // Chart 5: GMV by SKU Monthly (Bar Chart)
    gmvBySkuMonthly: {{
        type: 'bar',
        label: '各 SKU 每月 GMV (Monthly GMV by SKU)',
        xAxisLabel: '月份 (Month)',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_sku_monthly',
        multiDataset: true,
        colors: ['#1e40af', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#65a30d', '#f59e0b', '#6366f1']
    }},
    // Chart 6: Qty by SKU Daily (Line Chart)
    qtyBySkuDaily: {{
        type: 'line',
        label: '各 SKU 每日銷量 (Daily Qty by SKU)',
        xAxisLabel: '日期 (Date)',
        yAxisLabel: '銷量 (Quantity)',
        dataKey: 'qty_by_sku_daily',
        multiDataset: true,
        colors: ['#1e40af', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#65a30d', '#f59e0b', '#6366f1']
    }},
    // Chart 7: Qty by SKU Monthly (Bar Chart)
    qtyBySkuMonthly: {{
        type: 'bar',
        label: '各 SKU 每月銷量 (Monthly Qty by SKU)',
        xAxisLabel: '月份 (Month)',
        yAxisLabel: '銷量 (Quantity)',
        dataKey: 'qty_by_sku_monthly',
        multiDataset: true,
        colors: ['#1e40af', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#65a30d', '#f59e0b', '#6366f1']
    }},
    // Chart 8: GMV by Brand Daily (Bar Chart)
    gmvByBrandDaily: {{
        type: 'bar',
        label: '各品牌每日 GMV (Daily GMV by Brand)',
        xAxisLabel: '日期 (Date)',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_brand_daily',
        multiDataset: true,
        colors: ['#1e40af', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#65a30d', '#f59e0b', '#6366f1', '#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#84cc16']
    }},
    // Chart 9: GMV by Brand Monthly (Bar Chart)
    gmvByBrandMonthly: {{
        type: 'bar',
        label: '各品牌每月 GMV (Monthly GMV by Brand)',
        xAxisLabel: '月份 (Month)',
        yAxisLabel: 'GMV (HKD)',
        dataKey: 'gmv_by_brand_monthly',
        multiDataset: true,
        colors: ['#1e40af', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#65a30d', '#f59e0b', '#6366f1', '#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#84cc16']
    }}
}};

// Summary statistics
const salesSummary = {{
    totalGMV: {total_gmv:.2f},
    totalQty: {total_qty},
    totalOrders: {total_orders},
    uniqueSKUs: {unique_skus},
    uniqueBrands: {unique_brands},
    dateRange: '{date_range_min} - {date_range_max}',
    avgGMVPerOrder: {avg_gmv:.2f},
    topSKU: '{top_sku}',
    topBrand: '{top_brand}'
}};
'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print(f"Generated: {output_path}")
    return js_content

def main():
    print("Processing order report...")
    df = process_order_report()
    print(f"Loaded {len(df)} records")
    print(f"Date range: {df['DateStr'].min()} to {df['DateStr'].max()}")
    print(f"Unique SKUs: {df['SKU_ID'].nunique()}")
    print(f"Unique Brands: {df['Brand'].nunique()}")
    print(f"Total GMV: ${df['GMV'].sum():,.2f}")
    
    print("\nGenerating chart data...")
    chart_data = generate_chart_data(df)
    
    print("\nGenerating JavaScript file...")
    generate_js_file(chart_data, df, OUTPUT_FILE)
    
    print("\nDone!")
    return chart_data

if __name__ == '__main__':
    main()
