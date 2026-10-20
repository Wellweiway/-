import json, os, time, urllib.request
from urllib.parse import urlparse

UA = {"User-Agent": "Mozilla/5.0 (personal research)"}
os.makedirs("data/probe", exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()

def load_spec(swagger_url):
    status, body = get(swagger_url)
    spec = json.loads(body)
    u = urlparse(swagger_url)
    origin = u.scheme + "://" + u.netloc
    if "servers" in spec and spec["servers"]:
        s = spec["servers"][0]["url"]
        base = s if s.startswith("http") else origin + s
    else:
        host = spec.get("host", u.netloc)
        scheme = (spec.get("schemes") or ["https"])[0]
        base = scheme + "://" + host + spec.get("basePath", "")
    return spec, base

def short(v):
    if isinstance(v, dict):
        return {k: short(x) for k, x in v.items()}
    if isinstance(v, list):
        return [short(x) for x in v[:3]]
    if isinstance(v, str) and len(v) > 40:
        return v[:40] + "..."
    return v

def write_paths(spec, filename):
    lines = []
    for p, d in sorted(spec.get("paths", {}).items()):
        g = d.get("get", {})
        lines.append(p + "\t" + str(g.get("summary", "")))
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def probe(base, path):
    item = {"path": path}
    try:
        status, body = get(base + path)
        item["status"] = status
        data = json.loads(body)
        if isinstance(data, list):
            item["records"] = len(data)
            first = data[0] if data else None
        else:
            item["records"] = None
            first = data
        if isinstance(first, dict):
            item["fields"] = list(first.keys())
        item["sample"] = short(first)
        item["ok"] = True
    except Exception as e:
        item["ok"] = False
        item["error"] = repr(e)
    return item

TWSE_SWAGGER = "https://openapi.twse.com.tw/v1/swagger.json"
TPEX_SWAGGER = "https://www.tpex.org.tw/openapi/swagger.json"

TWSE_PATHS = [
    "/exchangeReport/BWIBBU_ALL", "/opendata/t187ap05_P",
    "/opendata/t187ap06_X_ci", "/opendata/t187ap07_X_ci",
    "/opendata/t187ap45_L", "/exchangeReport/TWTB4U",
    "/exchangeReport/TWTAWU", "/exchangeReport/MI_MARGN",
]
TPEX_PATHS = [
    "/tpex_mainboard_daily_close_quotes", "/tpex_mainboard_quotes",
    "/tpex_mainboard_peratio_analysis", "/tpex_3insti_daily_trading",
    "/tpex_3insti_trading", "/tpex_3insti_summary",
    "/tpex_mainboard_margin_balance", "/tpex_disposal_information",
    "/tpex_trading_warning_information",
    "/tpex_intraday_trading_statistics", "/tpex_exright_daily",
    "/mopsfin_t187ap05_O", "/mopsfin_t187ap06_O_ci",
    "/mopsfin_t187ap07_O_ci", "/mopsfin_t187ap03_O",
]

result = {"twse": {}, "tpex": {}}
for key, swagger, paths, pfile in [
    ("twse", TWSE_SWAGGER, TWSE_PATHS, "data/twse_paths.txt"),
    ("tpex", TPEX_SWAGGER, TPEX_PATHS, "data/tpex_paths.txt"),
]:
    try:
        spec, base = load_spec(swagger)
        write_paths(spec, pfile)
        result[key]["base_url"] = base
        result[key]["endpoints"] = []
        for p in paths:
            result[key]["endpoints"].append(probe(base, p))
            time.sleep(1.5)
    except Exception as e:
        result[key]["error"] = repr(e)

with open("data/probe/probe.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print("done")
