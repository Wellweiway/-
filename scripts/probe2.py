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
    if spec.get("servers"):
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
        return [short(x) for x in v[:2]]
    if isinstance(v, str) and len(v) > 40:
        return v[:40] + "..."
    return v

def dump_params(spec, filename):
    out = {}
    for p, d in spec.get("paths", {}).items():
        g = d.get("get", {})
        params = g.get("parameters", [])
        if params:
            out[p] = [
                {"name": x.get("name"), "in": x.get("in"),
                 "required": x.get("required"),
                 "type": x.get("type") or (x.get("schema") or {}).get("type"),
                 "ref": x.get("$ref")}
                for x in params
            ]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out

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

TWSE_PATHS = [
    "/opendata/t187ap03_L", "/opendata/t187ap05_L",
    "/opendata/t187ap06_L_ci", "/opendata/t187ap07_L_ci",
    "/announcement/punish", "/announcement/notice",
    "/exchangeReport/BWIBBU_d", "/holidaySchedule/holidaySchedule",
    "/indicesReport/TAI50I", "/indicesReport/MI_5MINS_HIST",
    "/exchangeReport/FMSRFK_ALL", "/exchangeReport/TWT84U",
    "/exchangeReport/STOCK_DAY_AVG_ALL",
    "/company/suspendListingCsvAndHtml",
]

result = {"twse": {}, "tpex": {}}
for key, swagger, paths, pfile in [
    ("twse", "https://openapi.twse.com.tw/v1/swagger.json",
     TWSE_PATHS, "data/probe/params_twse.json"),
    ("tpex", "https://www.tpex.org.tw/openapi/swagger.json",
     [], "data/probe/params_tpex.json"),
]:
    try:
        spec, base = load_spec(swagger)
        result[key]["params_count"] = len(dump_params(spec, pfile))
        result[key]["endpoints"] = []
        for p in paths:
            result[key]["endpoints"].append(probe(base, p))
            time.sleep(1.5)
    except Exception as e:
        result[key]["error"] = repr(e)

with open("data/probe/probe2.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print("done")
