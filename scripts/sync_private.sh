#!/bin/bash
# sync_private.sh — B0961005: copy index.html + data/ + reports/ to the PRIVATE repo + push
# B pilot (2026-08-29): 完整 dashboard 由 worker auth serve；gate 由 strip_gate 剝走
set -euo pipefail
SRC="${1:-/home/snkwok/B0961005-Inventory-Dashboard}"
DST=/home/snkwok/dashboard-private-data/B0961005
cd "$SRC"
mkdir -p "$DST/data" "$DST/reports"
# 只喺 index.html 係完整 dashboard（冇 dashFrame marker）先同步 —— loader 唔可以冚 private
if ! grep -q 'dashFrame' index.html 2>/dev/null; then
  cp -f index.html /tmp/b096_sync_index.html
  bash /home/snkwok/scripts/gate_strip_shared.sh /tmp/b096_sync_index.html B0961005 >/dev/null
  cp -f /tmp/b096_sync_index.html "$DST/index.html"
fi
cp -f data/*.csv data/*.json "$DST/data/" 2>/dev/null || true
cp -rf reports/* "$DST/reports/" 2>/dev/null || true
# 🛡️ 還原 public repo 個 index.html 做 loader（build 過程會 regenerate 有數據版——唔可以留喺 working tree）
git checkout -- index.html 2>/dev/null || true
git reset -q HEAD index.html 2>/dev/null || true
cd "$DST"
if git status --short | grep -q .; then
  git add -A
  git -c user.email="hermes@fificheck.local" -c user.name="Hermes" commit -q -m "B0961005 daily update $(date '+%F %T')"
  git push origin main -q
  echo "✅ private repo synced ($(date '+%F %T'))"
else
  echo "ℹ️ 冇嘢改 — skip push"
fi
