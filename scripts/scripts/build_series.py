import json, os, re

KEEP = 60
SRC = [
    ("twse_price", "Code", "ClosingPrice"),
    ("tpex_price", "SecuritiesCompanyCode", "Close"),
    ("twse_etf_price", "Code", "ClosingPrice"),
]


def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def num(x):
    try:
        v = float(str(x).replace(",", "").strip())
        return v if v > 0 else None
    except Exception:
        return None


def run():
    root = "data/history"
    dates = sorted(d for d in os.listdir(root) if re.match(r"^\d{4}-\d{2}-\d{2}$", d))[-KEEP:]
    by = {}
    for i, d in enumerate(dates):
        for name, ck, pk in SRC:
            j = load("%s/%s/%s.json" % (root, d, name))
            if not j:
                continue
            for r in j.get("records", []):
                c = str(r.get(ck, "")).strip()
                p = num(r.get(pk))
                if c and p is not None:
                    by.setdefault(c, {})[i] = round(p, 2)
    closes = {c: [m.get(i) for i in range(len(dates))] for c, m in sorted(by.items())}
    out = {"meta": {"dates": dates, "keep": KEEP,
                    "note": "各日收盤價,來源為 data/history;未還原除權息;null=當日沒有資料"},
           "closes": closes}
    os.makedirs("data/series", exist_ok=True)
    with open("data/series/closes.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("series:", len(dates), "days,", len(closes), "codes")


if __name__ == "__main__":
    run()
