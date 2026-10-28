import json, os, sys, time, hashlib, urllib.request
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "Mozilla/5.0 (personal research)"}
TW = timezone(timedelta(hours=8))
BASES = {
    "twse": "https://openapi.twse.com.tw/v1",
    "tpex": "https://www.tpex.org.tw/openapi/v1",
}
CODE_KEYS = ["Code", "SecuritiesCompanyCode", "公司代號", "股票代號", "基金代號"]
SLEEP = 1.5


def parse_date(raw):
    """支援民國7位(1151019)、西元8位(20261019)、民國斜線(115/09/01)。失敗回傳None。"""
    if raw is None:
        return None
    s = str(raw).strip()
    try:
        if "/" in s:
            y, m, d = [int(x) for x in s.split("/")]
            if y < 1911:
                y += 1911
        elif len(s) == 7 and s.isdigit():
            y, m, d = int(s[:3]) + 1911, int(s[3:5]), int(s[5:7])
        elif len(s) == 8 and s.isdigit():
            y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
        else:
            return None
        return datetime(y, m, d).date().isoformat()
    except Exception:
        return None


def code_of(rec):
    for k in CODE_KEYS:
        if k in rec:
            return str(rec[k]).strip()
    return None


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def fetch_json(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def D(name, market, path, kind, date_key=None, allow_empty=False,
      filt=True, fs=None, role=None, keep=None, min_rows=0,
      wlkey=None, usewl=None):
    return dict(name=name, market=market, path=path, kind=kind,
                date_key=date_key, allow_empty=allow_empty, filt=filt,
                fs=fs, role=role, keep=keep, min_rows=min_rows,
                wlkey=wlkey, usewl=usewl)


DATASETS = [
    # 公司名單(同時當作「只分析一般股票」的白名單)
    D("twse_company", "twse", "/opendata/t187ap03_L", "static", "出表日期",
      filt=False, role="company", min_rows=300,
      keep=["出表日期", "公司代號", "公司簡稱", "產業別", "上市日期",
            "已發行普通股數或TDR原股發行股數"]),
    D("tpex_company", "tpex", "/mopsfin_t187ap03_O", "static", "Date",
      filt=False, role="company", min_rows=300,
      keep=["Date", "SecuritiesCompanyCode", "CompanyAbbreviation",
            "SecuritiesIndustryCode", "DateOfListing", "IssueShares"]),
    # 上市 ETF:先抓基金名單當白名單,再從日行情挑出 ETF
    D("twse_fund_list", "twse", "/opendata/t187ap47_L", "static", "出表日期",
      filt=False, role="company", wlkey="twse_fund", min_rows=100,
      keep=["出表日期", "基金代號", "基金簡稱", "基金類型", "標的指數/追蹤指數名稱",
            "上市日期", "發行單位數/轉換數"]),
    D("twse_etf_price", "twse", "/exchangeReport/STOCK_DAY_ALL", "daily", "Date",
      usewl="twse_fund", min_rows=100),
    # 上市
    D("twse_price", "twse", "/exchangeReport/STOCK_DAY_ALL", "daily", "Date", min_rows=300),
    D("twse_valuation", "twse", "/exchangeReport/BWIBBU_d", "daily", "Date", min_rows=300),
    D("twse_margin", "twse", "/exchangeReport/MI_MARGN", "daily", None),
    D("twse_daytrade_list", "twse", "/exchangeReport/TWTB4U", "daily", "Date"),
    D("twse_punish", "twse", "/announcement/punish", "daily", "Date", allow_empty=True),
    D("twse_notice", "twse", "/announcement/notice", "daily", "Date", allow_empty=True),
    D("twse_halt", "twse", "/exchangeReport/TWTAWU", "static", None, allow_empty=True),
    D("twse_revenue", "twse", "/opendata/t187ap05_L", "static", "出表日期"),
    D("twse_income", "twse", "/opendata/t187ap06_L_ci", "static", "出表日期",
      fs=("公司代號", "年度", "季別")),
    D("twse_balance", "twse", "/opendata/t187ap07_L_ci", "static", "出表日期",
      fs=("公司代號", "年度", "季別")),
    D("twse_dividend", "twse", "/opendata/t187ap45_L", "static", "出表日期"),
    D("twse_holidays", "twse", "/holidaySchedule/holidaySchedule", "static", None, filt=False),
    D("twse_index_taiex", "twse", "/indicesReport/MI_5MINS_HIST", "daily", "Date", filt=False),
    D("twse_index_tw50", "twse", "/indicesReport/TAI50I", "daily", "Date", filt=False),
    D("twse_delisted", "twse", "/company/suspendListingCsvAndHtml", "static", None, filt=False),
    # 上櫃
    D("tpex_price", "tpex", "/tpex_mainboard_daily_close_quotes", "daily", "Date", min_rows=300),
    D("tpex_valuation", "tpex", "/tpex_mainboard_peratio_analysis", "daily", "Date", min_rows=300),
    D("tpex_institutional", "tpex", "/tpex_3insti_daily_trading", "daily", "Date"),
    D("tpex_margin", "tpex", "/tpex_mainboard_margin_balance", "daily", "Date"),
    D("tpex_disposal", "tpex", "/tpex_disposal_information", "daily", "Date", allow_empty=True),
    D("tpex_warning", "tpex", "/tpex_trading_warning_information", "daily", "Date", allow_empty=True),
    D("tpex_revenue", "tpex", "/mopsfin_t187ap05_O", "static", "出表日期"),
    D("tpex_income", "tpex", "/mopsfin_t187ap06_O_ci", "static", "Date",
      fs=("SecuritiesCompanyCode", "Year", "Season")),
    D("tpex_balance", "tpex", "/mopsfin_t187ap07_O_ci", "static", "Date",
      fs=("SecuritiesCompanyCode", "年度", "季別")),
]

# 只檢查「歷史涵蓋多長」,不儲存內容
RANGE_CHECKS = [
    ("twse_monthly_range", "twse", "/exchangeReport/FMSRFK_ALL", "Month", "1101"),
    ("twse_yearly_range", "twse", "/exchangeReport/FMNPTK_ALL", "Year", "1101"),
]


def process(cfg, whitelists, fetch_date, now_iso, first_seen, fetch):
    url = BASES[cfg["market"]] + cfg["path"]
    st = {"name": cfg["name"], "url": url}
    try:
        raw = fetch(url)
        if not isinstance(raw, list):
            raise ValueError("回傳不是清單")
        raw = [r for r in raw if isinstance(r, dict)]
        st["raw_count"] = len(raw)

        # 資料日期:取全部原始資料中最新的有效日期
        dd = None
        if cfg["date_key"]:
            ds = [parse_date(r.get(cfg["date_key"])) for r in raw]
            ds = [d for d in ds if d]
            dd = max(ds) if ds else None

        recs = raw
        if cfg["filt"]:
            wl = whitelists.get(cfg["usewl"] or cfg["market"])
            if not wl:
                raise ValueError("缺少公司名單,無法過濾")
            recs = [r for r in recs if code_of(r) in wl]
        if cfg["keep"]:
            recs = [{k: r.get(k) for k in cfg["keep"]} for r in recs]
        st["kept_count"] = len(recs)

        if not recs and not cfg["allow_empty"]:
            raise ValueError("過濾後沒有資料")
        if len(recs) < cfg["min_rows"]:
            raise ValueError("筆數過少(%d < %d),疑似不完整" % (len(recs), cfg["min_rows"]))
        if recs and cfg["date_key"] and not dd:
            raise ValueError("無法解析資料日期")
        if dd and dd > fetch_date:
            st["warning"] = "資料日期晚於抓取日"
        st["data_date"] = dd

        latest_path = "data/latest/%s.json" % cfg["name"]
        old = read_json(latest_path)
        old_dd = (old or {}).get("meta", {}).get("data_date")
        if dd and old_dd and dd < old_dd:
            st["result"] = "stale_skipped"
            return st, (old or {}).get("records")

        h = hashlib.sha256(
            json.dumps(recs, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        payload = {
            "meta": {
                "name": cfg["name"],
                "source_url": url,
                "fetched_at": now_iso,
                "data_date": dd,
                "date_note": None if cfg["date_key"] else "來源沒有日期欄位,以抓取日為準",
                "raw_count": len(raw),
                "kept_count": len(recs),
                "filtered_to_listed_companies": bool(cfg["filt"]),
                "content_hash": h,
            },
            "records": recs,
        }

        changed = not (old and old.get("meta", {}).get("content_hash") == h
                       and old.get("meta", {}).get("data_date") == dd)
        if changed:
            write_json(latest_path, payload)
            if cfg["kind"] == "daily":
                folder = dd or fetch_date
                write_json("data/history/%s/%s.json" % (folder, cfg["name"]), payload)
        st["result"] = "ok" if changed else "unchanged"

        # 財報「首次被本系統看到」的日期,供未來回測避免使用尚未公布的資料
        if cfg["fs"]:
            ck, yk, sk = cfg["fs"]
            for r in raw:
                c, y, s = r.get(ck), r.get(yk), r.get(sk)
                if c and y and s:
                    key = "%s|%s|%s|%s" % (cfg["name"], str(c).strip(), y, s)
                    if key not in first_seen:
                        first_seen[key] = fetch_date
        return st, recs
    except Exception as e:
        st["result"] = "failed"
        st["error"] = repr(e)
        return st, None


def range_check(name, market, path, key, sample_code, fetch):
    url = BASES[market] + path
    st = {"name": name, "url": url}
    try:
        raw = [r for r in fetch(url) if isinstance(r, dict)]
        vals = sorted({str(r.get(key)) for r in raw if r.get(key)})
        mine = sorted({str(r.get(key)) for r in raw
                       if r.get("Code") == sample_code and r.get(key)})
        st.update(rows=len(raw), distinct_periods=len(vals),
                  min=vals[0] if vals else None, max=vals[-1] if vals else None,
                  sample_code=sample_code, sample_code_periods=len(mine),
                  sample_first=mine[0] if mine else None,
                  sample_last=mine[-1] if mine else None, result="ok")
    except Exception as e:
        st["result"] = "failed"
        st["error"] = repr(e)
    return st


def main(fetch=fetch_json):
    now = datetime.now(TW)
    fetch_date = now.date().isoformat()
    first_seen = read_json("data/index/financials_first_seen.json") or {}
    whitelists = {}
    results = []
    for cfg in DATASETS:
        st, recs = process(cfg, whitelists, fetch_date, now.isoformat(), first_seen, fetch)
        if cfg["role"] == "company" and st["result"] == "failed":
            old = read_json("data/latest/%s.json" % cfg["name"])
            if old and old.get("records"):
                recs = old["records"]
                st["result"] = "fallback_cached"
                st["note"] = "本次抓取失敗,沿用上次成功的名單(資料日 %s)" % (old.get("meta", {}).get("data_date"),)
        results.append(st)
        if cfg["role"] == "company" and recs and st["result"] != "failed":
            whitelists[cfg["wlkey"] or cfg["market"]] = {code_of(r) for r in recs}
        time.sleep(SLEEP)
    ranges = []
    for name, market, path, key, code in RANGE_CHECKS:
        ranges.append(range_check(name, market, path, key, code, fetch))
        time.sleep(SLEEP)

    failed = [r for r in results + ranges if r["result"] == "failed"]
    status = {
        "run_at": now.isoformat(),
        "fetch_date": fetch_date,
        "failed_count": len(failed),
        "fallback_count": len([r for r in results if r["result"] == "fallback_cached"]),
        "datasets": results,
        "ranges": ranges,
        "whitelist_sizes": {k: len(v) for k, v in whitelists.items()},
    }
    write_json("data/status.json", status)
    write_json("data/index/financials_first_seen.json", first_seen)
    print(json.dumps({"failed": [(r["name"], r.get("error")) for r in failed],
                      "ok": len(results) + len(ranges) - len(failed)},
                     ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
