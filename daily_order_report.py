#!/usr/bin/env python3
"""
B0961005 Daily Order Report Automation
Runs as GitHub Actions cron job at 9am HKT daily.

Steps:
1. Login to MMS (merchant.shoalter.com)
2. Download TODAY's partial report for B0961005
3. Download YESTERDAY's final report for B0961005
4. Merge XLSX data into data/order_data.json
5. Update data/order_reports_manifest.json
6. Regenerate data/sales_trend_data.js
(GitHub Actions then commits and pushes)
"""

import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import openpyxl
from playwright.async_api import async_playwright, TimeoutError as PwTimeout

# ── Config ─────────────────────────────────────────────────────────────────────
MMS_URL  = "https://merchant.shoalter.com"
MMS_USER = "jerry@hktv.com.hk"
MMS_PASS = os.environ.get("MMS_PASSWORD", "JerRy111!!!!")
STORE_ID = "B0961005"
HKT      = timezone(timedelta(hours=8))

REPO_ROOT   = Path(__file__).parent
DATA_DIR    = REPO_ROOT / "data"
REPORTS_DIR = REPO_ROOT / "reports" / "order_reports"
MANIFEST    = DATA_DIR / "order_reports_manifest.json"
ORDER_DATA  = DATA_DIR / "order_data.json"
SALES_TREND = DATA_DIR / "sales_trend_data.js"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ── MMS Login & Download ───────────────────────────────────────────────────────

async def mms_login(page):
    print("🔐 Logging in to MMS...")
    await page.goto(MMS_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    # Fill email/username field
    email_filled = False
    for sel in [
        'input[type="email"]', 'input[name="email"]', 'input[name="username"]',
        'input[placeholder*="email" i]', 'input[placeholder*="Email"]',
        'input[placeholder*="帳號"]', 'input[placeholder*="用戶"]',
    ]:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.fill(MMS_USER)
                email_filled = True
                break
        except:
            pass
    if not email_filled:
        print("  ⚠️  Could not find email field — trying first visible text input")
        await page.locator('input[type="text"]').first.fill(MMS_USER)

    await page.fill('input[type="password"]', MMS_PASS)

    for sel in [
        'button[type="submit"]', 'input[type="submit"]',
        'button:has-text("登入")', 'button:has-text("Login")', 'button:has-text("Sign In")',
    ]:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                break
        except:
            pass

    await page.wait_for_load_state("networkidle", timeout=30000)
    print(f"  ✅ Logged in. URL: {page.url}")


async def navigate_to_order_report(page):
    """Navigate to the Daily Order Report section."""
    print("  Navigating to Order Report page...")

    # Try common direct URLs
    for suffix in [
        "/order/report", "/reports/order", "/report/order-list",
        "/order-report", "/merchant/report/order", "/report",
    ]:
        try:
            resp = await page.goto(f"{MMS_URL}{suffix}", wait_until="domcontentloaded", timeout=8000)
            if resp and resp.ok and "order" in page.url.lower():
                print(f"  Navigated via URL: {page.url}")
                return
        except:
            pass

    # Fall back: navigate via sidebar/menu
    cur_url = page.url
    for label in ["訂單報告", "Daily Order", "Order Report", "訂單", "報告", "Report"]:
        try:
            await page.click(f'text="{label}"', timeout=3000)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            if page.url != cur_url:
                print(f"  Navigated via menu '{label}': {page.url}")
                return
        except:
            pass

    print(f"  ⚠️  Could not confirm navigation. Current: {page.url}")


async def set_store_and_date(page, target_date: datetime):
    """Select store B0961005 and set the report date."""
    date_ymd = target_date.strftime("%Y-%m-%d")
    date_dmy = target_date.strftime("%d/%m/%Y")
    print(f"  Setting store={STORE_ID}, date={date_ymd}...")

    await page.wait_for_timeout(1000)

    # Select store
    for sel in [
        f'select[name*="store" i]', f'select[name*="merchant" i]',
        f'select[id*="store" i]', f'select[id*="merchant" i]', 'select',
    ]:
        locs = page.locator(sel)
        if await locs.count() > 0:
            for i in range(await locs.count()):
                try:
                    await locs.nth(i).select_option(value=STORE_ID, timeout=2000)
                    print(f"  Store selected.")
                    await page.wait_for_timeout(1000)
                    break
                except:
                    try:
                        await locs.nth(i).select_option(label=STORE_ID, timeout=2000)
                        break
                    except:
                        pass
            break

    # Set date via input[type=date]
    date_inputs = page.locator('input[type="date"]')
    if await date_inputs.count() > 0:
        n = await date_inputs.count()
        # If 2 date inputs (from/to), set both to same date
        for i in range(n):
            await date_inputs.nth(i).fill(date_ymd)
        print(f"  Date set: {date_ymd}")
        return

    # Set date via text input
    for placeholder in ["Date", "日期", "From", "開始", "Start", "YYYY", "yyyy"]:
        try:
            inp = page.locator(f'input[placeholder*="{placeholder}" i]').first
            if await inp.count() > 0 and await inp.is_visible():
                await inp.triple_click()
                await inp.type(date_dmy)
                print(f"  Date typed: {date_dmy}")
                return
        except:
            pass

    print(f"  ⚠️  Could not set date — proceed anyway")


async def click_download(page, target_date: datetime) -> Path | None:
    """Click Search (if any), then Export/Download and save the file."""

    # Click search/query if present
    for sel in [
        'button:has-text("搜尋")', 'button:has-text("查詢")', 'button:has-text("Search")',
        'input[type="submit"][value*="Search" i]', 'input[type="button"][value*="Search" i]',
    ]:
        try:
            if await page.locator(sel).count() > 0:
                await page.click(sel, timeout=3000)
                await page.wait_for_load_state("networkidle", timeout=20000)
                print("  Searched.")
                break
        except:
            pass

    # Click download/export
    download_selectors = [
        'button:has-text("匯出")', 'button:has-text("下載")',
        'button:has-text("Export")', 'button:has-text("Download")',
        'a:has-text("匯出")', 'a:has-text("下載")',
        'a:has-text("Export")', 'a:has-text("Download")',
        'input[type="submit"][value*="Export" i]', 'input[type="submit"][value*="Download" i]',
        'input[type="button"][value*="Export" i]', 'input[type="button"][value*="Download" i]',
    ]

    for sel in download_selectors:
        try:
            loc = page.locator(sel)
            if await loc.count() == 0:
                continue
            print(f"  Clicking download: {sel}")
            async with page.expect_download(timeout=60000) as dl_info:
                await loc.first.click(timeout=5000)
            dl = await dl_info.value
            fname     = dl.suggested_filename or f"ECOM-MMSNG_DAILY_ORDER_{STORE_ID}_{target_date.strftime('%Y%m%d')}000000.xlsx"
            save_path = REPORTS_DIR / fname
            await dl.save_as(save_path)
            print(f"  ✅ Saved: {fname}")
            return save_path
        except Exception as e:
            print(f"  Selector failed ({sel}): {e}")

    # Screenshot for debugging
    ss = REPO_ROOT / f"debug_{target_date.strftime('%Y%m%d')}.png"
    await page.screenshot(path=str(ss), full_page=True)
    print(f"  ❌ Download failed. Debug screenshot: {ss.name}")
    return None


async def download_report(page, target_date: datetime) -> Path | None:
    await navigate_to_order_report(page)
    await set_store_and_date(page, target_date)
    return await click_download(page, target_date)


async def mms_download(today: datetime, yesterday: datetime) -> dict:
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await ctx.new_page()
        try:
            await mms_login(page)
            print(f"\n📅 TODAY ({today.strftime('%Y-%m-%d')}) — partial")
            results["today"] = await download_report(page, today)
            print(f"\n📅 YESTERDAY ({yesterday.strftime('%Y-%m-%d')}) — final")
            results["yesterday"] = await download_report(page, yesterday)
        finally:
            await browser.close()
    return results


# ── XLSX Parsing ───────────────────────────────────────────────────────────────

def parse_xlsx(xlsx_path: Path) -> dict:
    """Parse order report XLSX (data rows start at row 6). Returns aggregated data."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.active

    gmv_daily         = defaultdict(float)
    gmv_hourly        = defaultdict(lambda: defaultdict(float))
    gmv_sku_daily     = defaultdict(lambda: defaultdict(float))
    qty_sku_daily     = defaultdict(lambda: defaultdict(float))
    gmv_brand_daily   = defaultdict(lambda: defaultdict(float))
    order_count_daily = defaultdict(int)
    sku_names         = {}
    sku_brand_map     = {}
    brand_names       = {}

    for row in ws.iter_rows(min_row=6, values_only=True):
        order_date = row[6]   # G: Order Date
        order_time = row[7]   # H: Order Time
        sku_id_raw = row[17]  # R: SKU ID
        brand_cn   = row[19]  # T: Brand (Chinese)
        sku_name   = row[21]  # V: SKU Name (Chinese)
        qty        = row[23]  # X: Qty
        gmv        = row[26]  # AA: GMV

        if not order_date or not sku_id_raw:
            continue

        date_str = str(order_date)[:10]
        if not date_str or len(date_str) < 10:
            continue

        hour = 0
        if order_time:
            ts = str(order_time)
            if ":" in ts:
                try:
                    hour = int(ts.split(":")[0])
                except:
                    pass

        full_sku = f"B0961005_S_{sku_id_raw}"
        brand    = str(brand_cn) if brand_cn else "Unknown"

        try:
            qty_val = float(qty) if qty else 0
            gmv_val = float(gmv) if gmv else 0
        except:
            qty_val = gmv_val = 0

        gmv_daily[date_str]                  += gmv_val
        gmv_hourly[date_str][f"{hour:02d}"]  += gmv_val
        gmv_sku_daily[full_sku][date_str]    += gmv_val
        qty_sku_daily[full_sku][date_str]    += qty_val
        gmv_brand_daily[brand][date_str]     += gmv_val
        order_count_daily[date_str]          += 1
        sku_names[full_sku]                   = str(sku_name) if sku_name else full_sku
        sku_brand_map[full_sku]               = brand
        brand_names[brand]                    = brand

    return {
        "gmv_daily":         dict(gmv_daily),
        "gmv_hourly":        {k: dict(v) for k, v in gmv_hourly.items()},
        "gmv_sku_daily":     {k: dict(v) for k, v in gmv_sku_daily.items()},
        "qty_sku_daily":     {k: dict(v) for k, v in qty_sku_daily.items()},
        "gmv_brand_daily":   {k: dict(v) for k, v in gmv_brand_daily.items()},
        "order_count_daily": dict(order_count_daily),
        "sku_names":         sku_names,
        "sku_brand_map":     sku_brand_map,
        "brand_names":       brand_names,
    }


def merge_into_order_data(new_data: dict):
    """Merge per-date data from a new XLSX into the existing order_data.json."""
    if ORDER_DATA.exists():
        existing = json.loads(ORDER_DATA.read_text(encoding="utf-8"))
    else:
        existing = {k: {} for k in [
            "gmv_daily", "gmv_hourly", "gmv_sku_daily", "qty_sku_daily",
            "gmv_brand_daily", "order_count_daily", "sku_names", "sku_brand_map", "brand_names",
        ]}

    # Replace per-date scalars
    existing["gmv_daily"].update(new_data["gmv_daily"])
    existing["order_count_daily"].update(new_data["order_count_daily"])
    existing["gmv_hourly"].update(new_data["gmv_hourly"])

    # Merge nested SKU/brand dicts (replace per-date values)
    for sku, dates in new_data["gmv_sku_daily"].items():
        existing["gmv_sku_daily"].setdefault(sku, {}).update(dates)
    for sku, dates in new_data["qty_sku_daily"].items():
        existing["qty_sku_daily"].setdefault(sku, {}).update(dates)
    for brand, dates in new_data["gmv_brand_daily"].items():
        existing["gmv_brand_daily"].setdefault(brand, {}).update(dates)

    existing["sku_names"].update(new_data["sku_names"])
    existing["sku_brand_map"].update(new_data["sku_brand_map"])
    existing["brand_names"].update(new_data["brand_names"])

    ORDER_DATA.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ order_data.json updated")


# ── Manifest ───────────────────────────────────────────────────────────────────

def date_to_chinese(dt: datetime) -> str:
    return f"{dt.month}月{dt.day}日"


def update_manifest(xlsx_path: Path, gmv_total: float, target_date: datetime):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []

    date_cn = date_to_chinese(target_date)
    fname   = xlsx_path.name

    # Extract HH:MM from filename timestamp (YYYYMMDDHHMMSS)
    ts = "unknown"
    m = re.search(r"_(\d{8})(\d{6})\.xlsx$", fname)
    if m:
        t = m.group(2)
        ts = f"{t[:2]}:{t[2:4]}"

    entry = {"date": date_cn, "gmv": f"${gmv_total:,.2f}", "timestamp": ts, "filename": fname}

    # Replace existing entry for same date, or prepend
    dates_in_manifest = [e["date"] for e in manifest]
    if date_cn in dates_in_manifest:
        manifest[dates_in_manifest.index(date_cn)] = entry
    else:
        manifest.insert(0, entry)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ Manifest: {date_cn} GMV={entry['gmv']} @{ts}")


# ── Regenerate sales_trend_data.js ─────────────────────────────────────────────

def regenerate_sales_trend():
    d = json.loads(ORDER_DATA.read_text(encoding="utf-8"))

    gmv_daily      = d["gmv_daily"]
    gmv_hourly     = d["gmv_hourly"]
    qty_sku_daily  = d["qty_sku_daily"]
    gmv_sku_daily  = d["gmv_sku_daily"]
    gmv_brand_daily= d["gmv_brand_daily"]
    sku_names      = d["sku_names"]
    sku_brand_map  = d["sku_brand_map"]
    order_count    = d["order_count_daily"]

    dates       = sorted(gmv_daily.keys())
    labels_date = dates[::-1]
    data_date   = [round(gmv_daily.get(ds, 0), 2) for ds in labels_date]
    gmv_monthly_total = round(sum(gmv_daily.values()), 2)

    all_hours = [f"{h:02d}" for h in range(24)]
    gmv_hour  = [round(sum(gmv_hourly.get(ds, {}).get(f"{h:02d}", 0) for ds in dates), 2) for h in range(24)]

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_labels, dow_data = [], []
    for ds in labels_date:
        idx = datetime.strptime(ds, "%Y-%m-%d").weekday()
        dow_labels.append(f"{DAY_NAMES[idx]} ({ds})")
        dow_data.append(round(gmv_daily.get(ds, 0), 2))

    order_arr = [order_count.get(ds, 0) for ds in labels_date]

    sku_totals = {sku: sum(dv.values()) for sku, dv in gmv_sku_daily.items()}
    top_skus   = sorted(sku_totals, key=lambda x: -sku_totals[x])[:50]
    sku_data   = [[round(gmv_sku_daily.get(s, {}).get(ds, 0), 2) for ds in labels_date] for s in top_skus]
    qty_data   = [[round(qty_sku_daily.get(s, {}).get(ds, 0), 2) for ds in labels_date] for s in top_skus]

    brand_totals = {b: sum(dv.values()) for b, dv in gmv_brand_daily.items()}
    top_brands   = sorted(brand_totals, key=lambda x: -brand_totals[x])[:20]
    brand_data   = [[round(gmv_brand_daily.get(b, {}).get(ds, 0), 2) for ds in labels_date] for b in top_brands]

    # Monthly aggregations
    gmv_sku_m   = defaultdict(lambda: defaultdict(float))
    qty_sku_m   = defaultdict(lambda: defaultdict(float))
    gmv_brand_m = defaultdict(lambda: defaultdict(float))
    for sku, dv in gmv_sku_daily.items():
        for ds, v in dv.items():
            gmv_sku_m[ds[:7]][sku] += v
    for sku, dv in qty_sku_daily.items():
        for ds, v in dv.items():
            qty_sku_m[ds[:7]][sku] += v
    for brand, dv in gmv_brand_daily.items():
        for ds, v in dv.items():
            gmv_brand_m[ds[:7]][brand] += v

    month_labels       = sorted(gmv_sku_m.keys())
    sku_monthly_data   = [[round(gmv_sku_m.get(m, {}).get(s, 0), 2) for m in month_labels] for s in top_skus]
    qty_monthly_data   = [[round(qty_sku_m.get(m, {}).get(s, 0), 2) for m in month_labels] for s in top_skus]
    brand_monthly_data = [[round(gmv_brand_m.get(m, {}).get(b, 0), 2) for m in month_labels] for b in top_brands]

    total_gmv    = round(sum(gmv_daily.values()), 2)
    total_orders = sum(order_count.values())
    avg_order    = round(total_gmv / total_orders, 2) if total_orders else 0

    gmv_by_dh = {
        ds: [round(gmv_hourly.get(ds, {}).get(f"{h:02d}", 0), 2) for h in range(24)]
        for ds in labels_date
    }

    chart_data = {
        "gmv_by_date":          {"labels": labels_date, "data": data_date},
        "gmv_by_month":         {"labels": month_labels, "data": [gmv_monthly_total]},
        "gmv_by_hour":          {"labels": all_hours, "data": gmv_hour},
        "gmv_by_day_of_week":   {"labels": dow_labels, "data": dow_data},
        "gmv_by_date_hour":     {"labels": labels_date, "hours": all_hours, "data": gmv_by_dh},
        "orders_by_date":       {"labels": labels_date, "data": order_arr},
        "gmv_by_sku_daily":     {"labels": labels_date, "skus": top_skus, "data": sku_data},
        "qty_by_sku_daily":     {"labels": labels_date, "skus": top_skus, "data": qty_data},
        "gmv_by_sku_monthly":   {"labels": month_labels, "skus": top_skus, "data": sku_monthly_data},
        "qty_by_sku_monthly":   {"labels": month_labels, "skus": top_skus, "data": qty_monthly_data},
        "gmv_by_brand_daily":   {"labels": labels_date, "brands": top_brands, "data": brand_data},
        "gmv_by_brand_monthly": {"labels": month_labels, "brands": top_brands, "data": brand_monthly_data},
        "sku_name_map":         sku_names,
        "sku_brand_map":        sku_brand_map,
        "summary": {
            "total_gmv":       total_gmv,
            "total_orders":    total_orders,
            "avg_order_value": avg_order,
            "date_range":      f"{labels_date[-1]} to {labels_date[0]}" if labels_date else "",
        },
    }

    js = (
        f"// Auto-generated sales trend data\n"
        f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"// Source: All daily order reports (combined)\n\n"
        f"const salesTrendData = {json.dumps(chart_data, ensure_ascii=False, indent=2)};\n"
    )

    SALES_TREND.write_text(js, encoding="utf-8")
    print(f"  ✅ sales_trend_data.js regenerated ({len(js):,} bytes)")


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    now       = datetime.now(tz=HKT)
    today     = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    print("=" * 55)
    print(f"B0961005 Daily Order Report — {now.strftime('%Y-%m-%d %H:%M HKT')}")
    print(f"TODAY:     {today.strftime('%Y-%m-%d')}  (partial)")
    print(f"YESTERDAY: {yesterday.strftime('%Y-%m-%d')}  (final)")
    print("=" * 55)

    # Step 1–2: Download from MMS
    files = await mms_download(today, yesterday)

    # Step 3–4: Process each file
    changed = False
    for label, target_date, key in [
        ("YESTERDAY", yesterday, "yesterday"),
        ("TODAY",     today,     "today"),
    ]:
        xlsx_path = files.get(key)
        if not xlsx_path or not xlsx_path.exists():
            print(f"\n⚠️  No XLSX for {label}, skipping.")
            continue

        print(f"\n📊 Processing {label}: {xlsx_path.name}")
        new_data  = parse_xlsx(xlsx_path)
        gmv_total = sum(new_data["gmv_daily"].values())
        orders    = sum(new_data["order_count_daily"].values())
        print(f"  Orders={orders:,}  GMV=${gmv_total:,.2f}")

        merge_into_order_data(new_data)
        update_manifest(xlsx_path, gmv_total, target_date)
        changed = True

    if not changed:
        print("\nℹ️  No new data. Exiting without commit.")
        sys.exit(0)

    # Step 5: Regenerate JS
    print("\n🔄 Regenerating sales_trend_data.js...")
    regenerate_sales_trend()

    print("\n✅ All done! GitHub Actions will commit and push.")


if __name__ == "__main__":
    asyncio.run(main())
