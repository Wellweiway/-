import json, os, sys, urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (personal research)"}
os.makedirs("data/latest", exist_ok=True)
report = {"run_utc": datetime.now(timezone.utc).isoformat(), "checks": []}
failed = False

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()

# 檢查 1:證交所上市個股日成交
item = {"name": "TWSE STOCK_DAY_ALL"}
try:
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    item["url"] = url
    status, body = get(url)
    data = json.loads(body)
    item["status"] = status
    item["records"] = len(data)
    item["data_date_raw"] = data[0].get("Date") if data else None
    item["sample"] = data[0] if data else None
    if not data:
        raise ValueError("empty data")
    with open("data/latest/twse_stock_day_all.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    item["ok"] = True
except Exception as e:
    item["ok"] = False
    item["error"] = repr(e)
    failed = True
report["checks"].append(item)

# 檢查 2:櫃買中心 API 規格(只列出可用路徑,供下一步核對)
item = {"name": "TPEx swagger"}
try:
    url = "https://www.tpex.org.tw/openapi/swagger.json"
    item["url"] = url
    status, body = get(url)
    spec = json.loads(body)
    paths = sorted(spec.get("paths", {}).keys())
    item["status"] = status
    item["path_count"] = len(paths)
    with open("data/tpex_paths.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(paths))
    item["ok"] = True
except Exception as e:
    item["ok"] = False
    item["error"] = repr(e)
    failed = True
report["checks"].append(item)

with open("data/meta.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2)[:3000])
sys.exit(1 if failed else 0)
