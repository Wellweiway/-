import json, os, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (personal research)"}
def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())
os.makedirs("data/probe", exist_ok=True)
W = "https://openapi.twse.com.tw/v1"
T = "https://www.tpex.org.tw/openapi/v1"
CODES = ["0050", "0056", "00878", "00679B", "00919"]
out = {}
try:
    fund = get(W + "/opendata/t187ap47_L")
    out["fund_list"] = {
        "records": len(fund),
        "fields": list(fund[0].keys()) if fund else None,
        "sample": fund[:3],
        "matches": [r for r in fund if any(c in json.dumps(r, ensure_ascii=False) for c in CODES)][:5],
    }
except Exception as e:
    out["fund_list"] = {"error": repr(e)}
for name, url, key in [
    ("twse_price", W + "/exchangeReport/STOCK_DAY_ALL", "Code"),
    ("twse_valuation", W + "/exchangeReport/BWIBBU_d", "Code"),
    ("tpex_price", T + "/tpex_mainboard_daily_close_quotes", "SecuritiesCompanyCode"),
]:
    try:
        rows = get(url)
        out[name] = {"records": len(rows),
                     "matches": [r for r in rows if str(r.get(key, "")).strip() in CODES]}
    except Exception as e:
        out[name] = {"error": repr(e)}
with open("data/probe/probe3.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("done")
