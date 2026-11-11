
import json
import os
import sys
import time
import hashlib
import gzip
import urllib.request
import csv
import io
import re
import unicodedata

from datetime import datetime, timezone, timedelta


UA = {
    "User-Agent": "Mozilla/5.0 (personal research)",
    "Accept-Encoding": "gzip"
}

TW = timezone(timedelta(hours=8))

BASES = {
    "twse": "https://openapi.twse.com.tw/v1",
    "tpex": "https://www.tpex.org.tw/openapi/v1",
}

CODE_KEYS = [
    "Code",
    "SecuritiesCompanyCode",
    "公司代號",
    "股票代號",
    "基金代號"
]

SLEEP = 1.5


# =========================================================
# 資料格式正規化
# =========================================================

def normalize_text(value):
    if value is None:
        return ""

    return unicodedata.normalize(
        "NFKC",
        str(value).replace("\ufeff", "")
    ).strip()


def normalize_key(value):
    return re.sub(r"\s+", "", normalize_text(value))


def get_field(record, wanted):
    if not isinstance(record, dict):
        return None

    target = normalize_key(wanted)

    if wanted in record:
        return record[wanted]

    for key, value in record.items():
        if normalize_key(key) == target:
            return value

    return None


def parse_date(raw):
    """
    支援：
    民國日期：1151102、115/11/02
    西元日期：20261102、2026/11/02
    全形數字、引號、空白及其他分隔符號。
    """

    if raw is None:
        return None

    s = normalize_text(raw).strip().strip('"').strip("'")

    if not s:
        return None

    try:
        parts = re.findall(r"\d+", s)

        if len(parts) == 3:
            y, m, d = [int(x) for x in parts]

            if y < 1911:
                y += 1911

            return datetime(y, m, d).date().isoformat()

        digits = re.sub(r"\D", "", s)

        if len(digits) == 7:
            y = int(digits[:3]) + 1911
            m = int(digits[3:5])
            d = int(digits[5:7])

        elif len(digits) == 8:
            y = int(digits[:4])
            m = int(digits[4:6])
            d = int(digits[6:8])

        else:
            return None

        return datetime(y, m, d).date().isoformat()

    except (TypeError, ValueError):
        return None


def code_of(rec):
    for k in CODE_KEYS:
        value = get_field(rec, k)

        if value is not None and str(value).strip():
            return str(value).strip()

    return None


# =========================================================
# JSON 讀寫
# =========================================================

def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return None


def write_json(path, obj):
    folder = os.path.dirname(path)

    if folder:
        os.makedirs(folder, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            obj,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )


# =========================================================
# API 資料抓取：支援 JSON、CSV、GZIP
# =========================================================

def fetch_json(url, tries=4):
    last = None

    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)

            with urllib.request.urlopen(req, timeout=60) as r:
                status = getattr(r, "status", "unknown")

                content_type = r.headers.get(
                    "Content-Type", "unknown"
                )

                content_encoding = (
                    r.headers.get("Content-Encoding") or ""
                ).lower()

                body = r.read()

            if content_encoding == "gzip" or body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)

            if not body or not body.strip():
                raise ValueError(
                    f"API 回傳空白內容 "
                    f"(HTTP {status}, Content-Type: {content_type})"
                )

            text = body.decode("utf-8-sig").strip()

            if not text:
                raise ValueError("API 回傳內容解碼後為空白")

            # CSV
            if "csv" in content_type.lower():

                reader = csv.DictReader(
                    io.StringIO(text, newline="")
                )

                data = []

                for row in reader:
                    clean_row = {}

                    for key, value in row.items():
                        clean_key = normalize_text(key)

                        clean_value = (
                            normalize_text(value)
                            if value is not None
                            else None
                        )

                        clean_row[clean_key] = clean_value

                    data.append(clean_row)

                if not data:
                    raise ValueError("API 回傳 CSV 沒有資料")

                if not any(
                    key and str(key).strip()
                    for key in data[0].keys()
                ):
                    raise ValueError("CSV 沒有有效欄位名稱")

            # JSON
            else:
                try:
                    data = json.loads(text)

                except json.JSONDecodeError as e:
                    preview = (
                        text[:200]
                        .replace("\n", " ")
                        .replace("\r", " ")
                    )

                    raise ValueError(
                        f"API 回傳不是有效 JSON "
                        f"(HTTP {status}, Content-Type: {content_type})；"
                        f"內容開頭：{preview!r}"
                    ) from e

            return data

        except Exception as e:
            last = e

            if i < tries - 1:
                time.sleep(3 * (i + 1))

    raise RuntimeError(
        f"下載資料失敗，共嘗試 {tries} 次：{url}；"
        f"最後錯誤：{last!r}"
    ) from last


# =========================================================
# 資料集設定
# =========================================================

def D(
    name,
    market,
    path,
    kind,
    date_key=None,
    allow_empty=False,
    filt=True,
    fs=None,
    role=None,
    keep=None,
    min_rows=0,
    wlkey=None,
    usewl=None
):
    return dict(
        name=name,
        market=market,
        path=path,
        kind=kind,
        date_key=date_key,
        allow_empty=allow_empty,
        filt=filt,
        fs=fs,
        role=role,
        keep=keep,
        min_rows=min_rows,
        wlkey=wlkey,
        usewl=usewl
    )


DATASETS = [

    # 公司名單
    D(
        "twse_company", "twse",
        "/opendata/t187ap03_L", "static", "出表日期",
        filt=False, role="company", min_rows=300,
        keep=[
            "出表日期", "公司代號", "公司簡稱", "產業別",
            "上市日期", "已發行普通股數或TDR原股發行股數"
        ]
    ),

    D(
        "tpex_company", "tpex",
        "/mopsfin_t187ap03_O", "static", "Date",
        filt=False, role="company", min_rows=300,
        keep=[
            "Date", "SecuritiesCompanyCode",
            "CompanyAbbreviation", "SecuritiesIndustryCode",
            "DateOfListing", "IssueShares"
        ]
    ),

    # ETF 名單
    D(
        "twse_fund_list", "twse",
        "/opendata/t187ap47_L", "static", "出表日期",
        filt=False, role="company", wlkey="twse_fund",
        min_rows=100,
        keep=[
            "出表日期", "基金代號", "基金簡稱", "基金類型",
            "標的指數/追蹤指數名稱", "上市日期",
            "發行單位數/轉換數"
        ]
    ),

    D(
        "twse_etf_price", "twse",
        "/exchangeReport/STOCK_DAY_ALL", "daily", "Date",
        usewl="twse_fund", min_rows=100
    ),

    # 上市股票
    D(
        "twse_price", "twse",
        "/exchangeReport/STOCK_DAY_ALL", "daily", "Date",
        min_rows=300
    ),

    D(
        "twse_valuation", "twse",
        "/exchangeReport/BWIBBU_d", "daily", "Date",
        min_rows=300
    ),

    D(
        "twse_margin", "twse",
        "/exchangeReport/MI_MARGN", "daily", None
    ),

    D(
        "twse_daytrade_list", "twse",
        "/exchangeReport/TWTB4U", "daily", "Date"
    ),

    D(
        "twse_punish", "twse",
        "/announcement/punish", "daily", "Date",
        allow_empty=True
    ),

    D(
        "twse_notice", "twse",
        "/announcement/notice", "daily", "Date",
        allow_empty=True
    ),

    D(
        "twse_halt", "twse",
        "/exchangeReport/TWTAWU", "static", None,
        allow_empty=True
    ),

    D(
        "twse_revenue", "twse",
        "/opendata/t187ap05_L", "static", "出表日期"
    ),

    D(
        "twse_income", "twse",
        "/opendata/t187ap06_L_ci", "static", "出表日期",
        fs=("公司代號", "年度", "季別")
    ),

    D(
        "twse_balance", "twse",
        "/opendata/t187ap07_L_ci", "static", "出表日期",
        fs=("公司代號", "年度", "季別")
    ),

    D(
        "twse_dividend", "twse",
        "/opendata/t187ap45_L", "static", "出表日期"
    ),

    D(
        "twse_holidays", "twse",
        "/holidaySchedule/holidaySchedule", "static", None,
        filt=False
    ),

    D(
        "twse_index_taiex", "twse",
        "/indicesReport/MI_5MINS_HIST", "daily", "Date",
        filt=False
    ),

    # 臺灣50指數 CSV
    D(
        "twse_index_tw50", "twse",
        "/indicesReport/TAI50I", "daily", "日期",
        filt=False
    ),

    # 終止上市公司
    D(
        "twse_delisted", "twse",
        "/company/suspendListingCsvAndHtml", "static", None,
        filt=False
    ),

    # 上櫃股票
    D(
        "tpex_price", "tpex",
        "/tpex_mainboard_quotes", "daily", "Date",
        min_rows=700
    ),

    D(
        "tpex_valuation", "tpex",
        "/tpex_mainboard_peratio_analysis", "daily", "Date",
        min_rows=300
    ),

    D(
        "tpex_institutional", "tpex",
        "/tpex_3insti_daily_trading", "daily", "Date"
    ),

    D(
        "tpex_margin", "tpex",
        "/tpex_mainboard_margin_balance", "daily", "Date"
    ),

    D(
        "tpex_disposal", "tpex",
        "/tpex_disposal_information", "daily", "Date",
        allow_empty=True
    ),

    D(
        "tpex_warning", "tpex",
        "/tpex_trading_warning_information", "daily", "Date",
        allow_empty=True
    ),

    D(
        "tpex_revenue", "tpex",
        "/mopsfin_t187ap05_O", "static", "出表日期"
    ),

    D(
        "tpex_income", "tpex",
        "/mopsfin_t187ap06_O_ci", "static", "Date",
        fs=("SecuritiesCompanyCode", "Year", "Season")
    ),

    D(
        "tpex_balance", "tpex",
        "/mopsfin_t187ap07_O_ci", "static", "Date",
        fs=("SecuritiesCompanyCode", "年度", "季別")
    ),
]


# 歷史資料涵蓋範圍檢查
RANGE_CHECKS = [
    (
        "twse_monthly_range", "twse",
        "/exchangeReport/FMSRFK_ALL", "Month", "1101"
    ),
    (
        "twse_yearly_range", "twse",
        "/exchangeReport/FMNPTK_ALL", "Year", "1101"
    ),
]


# =========================================================
# 主要資料處理
# =========================================================

def process(cfg, whitelists, fetch_date, now_iso, first_seen, fetch):

    url = BASES[cfg["market"]] + cfg["path"]

    st = {
        "name": cfg["name"],
        "url": url
    }

    latest_path = "data/latest/%s.json" % cfg["name"]

    try:

        raw = fetch(url)

        if not isinstance(raw, list):
            raise ValueError("回傳不是清單")

        raw = [
            r for r in raw
            if isinstance(r, dict)
        ]

        st["raw_count"] = len(raw)

        # 取得資料日期
        dd = None

        if cfg["date_key"]:

            ds = [
                parse_date(get_field(r, cfg["date_key"]))
                for r in raw
            ]

            ds = [
                d for d in ds
                if d
            ]

            dd = max(ds) if ds else None

        recs = raw

        # 公司名單過濾
        if cfg["filt"]:

            wl = whitelists.get(
                cfg["usewl"] or cfg["market"]
            )

            if not wl:
                raise ValueError("缺少公司名單，無法過濾")

            recs = [
                r for r in recs
                if code_of(r) in wl
            ]

        # 保留指定欄位
        if cfg["keep"]:

            recs = [
                {
                    k: get_field(r, k)
                    for k in cfg["keep"]
                }
                for r in recs
            ]

        st["kept_count"] = len(recs)

        if not recs and not cfg["allow_empty"]:
            raise ValueError("過濾後沒有資料")

        if len(recs) < cfg["min_rows"]:
            raise ValueError(
                "筆數過少(%d < %d)，疑似不完整"
                % (len(recs), cfg["min_rows"])
            )

        # 日期錯誤時輸出實際欄位及範例
        if recs and cfg["date_key"] and not dd:

            available_keys = (
                list(raw[0].keys())[:20]
                if raw else []
            )

            sample_value = (
                get_field(raw[0], cfg["date_key"])
                if raw else None
            )

            raise ValueError(
                "無法解析資料日期；"
                "設定日期欄位=%r；"
                "實際欄位=%r；"
                "日期欄位範例值=%r"
                % (
                    cfg["date_key"],
                    available_keys,
                    sample_value
                )
            )

        if dd and dd > fetch_date:
            st["warning"] = "資料日期晚於抓取日"

        st["data_date"] = dd

        old = read_json(latest_path)

        old_dd = (
            (old or {})
            .get("meta", {})
            .get("data_date")
        )

        # 避免舊資料覆蓋新資料
        if dd and old_dd and dd < old_dd:

            st["result"] = "stale_skipped"

            return st, (old or {}).get("records")

        # 計算雜湊值
        h = hashlib.sha256(
            json.dumps(
                recs,
                ensure_ascii=False,
                sort_keys=True
            ).encode("utf-8")
        ).hexdigest()

        payload = {
            "meta": {
                "name": cfg["name"],
                "source_url": url,
                "fetched_at": now_iso,
                "data_date": dd,
                "date_note": (
                    None if cfg["date_key"]
                    else "來源沒有日期欄位，以抓取日為準"
                ),
                "raw_count": len(raw),
                "kept_count": len(recs),
                "filtered_to_listed_companies": bool(cfg["filt"]),
                "content_hash": h,
            },
            "records": recs,
        }

        changed = not (
            old
            and old.get("meta", {}).get("content_hash") == h
            and old.get("meta", {}).get("data_date") == dd
        )

        if changed:

            write_json(latest_path, payload)

            if cfg["kind"] == "daily":

                folder = dd or fetch_date

                write_json(
                    "data/history/%s/%s.json"
                    % (folder, cfg["name"]),
                    payload
                )

        st["result"] = (
            "ok" if changed
            else "unchanged"
        )

        # 財報首次被系統看到的日期
        if cfg["fs"]:

            ck, yk, sk = cfg["fs"]

            for r in raw:

                c = get_field(r, ck)
                y = get_field(r, yk)
                s = get_field(r, sk)

                if c and y and s:

                    key = "%s|%s|%s|%s" % (
                        cfg["name"],
                        str(c).strip(),
                        y,
                        s
                    )

                    if key not in first_seen:
                        first_seen[key] = fetch_date

        return st, recs

    except Exception as e:

        st["result"] = "failed"
        st["error"] = repr(e)

        # 特定資料來源失敗時沿用舊資料
        if cfg["name"] in (
            "twse_revenue",
            "tpex_revenue",
            "twse_delisted"
        ):

            old = read_json(latest_path)

            if (
                old
                and isinstance(old.get("records"), list)
                and old["records"]
            ):

                old_dd = (
                    old.get("meta", {})
                    .get("data_date")
                )

                st["result"] = "fallback_cached"
                st["data_date"] = old_dd
                st["kept_count"] = len(old["records"])

                st["note"] = (
                    "本次資料抓取失敗，沿用上次成功資料；"
                    "資料日期為 %s，並非本次更新"
                    % (old_dd or "未知")
                )

                return st, old["records"]

            # 終止上市資料不是行情計算必要資料
            if cfg["name"] == "twse_delisted":

                st["result"] = "unavailable_optional"

                st["note"] = (
                    "終止上市公司資料來源暫時無法取得，"
                    "目前沒有可沿用的舊資料。"
                )

                return st, None

        return st, None


# =========================================================
# 歷史資料範圍檢查
# =========================================================

def range_check(name, market, path, key, sample_code, fetch):

    url = BASES[market] + path

    st = {
        "name": name,
        "url": url
    }

    try:

        raw = [
            r for r in fetch(url)
            if isinstance(r, dict)
        ]

        vals = sorted({
            str(get_field(r, key))
            for r in raw
            if get_field(r, key)
        })

        mine = sorted({
            str(get_field(r, key))
            for r in raw
            if str(get_field(r, "Code")) == sample_code
            and get_field(r, key)
        })

        st.update(
            rows=len(raw),
            distinct_periods=len(vals),
            min=vals[0] if vals else None,
            max=vals[-1] if vals else None,
            sample_code=sample_code,
            sample_code_periods=len(mine),
            sample_first=mine[0] if mine else None,
            sample_last=mine[-1] if mine else None,
            result="ok"
        )

    except Exception as e:

        st["result"] = "failed"
        st["error"] = repr(e)

    return st


# =========================================================
# 主程式
# =========================================================

def main(fetch=fetch_json):

    now = datetime.now(TW)

    fetch_date = now.date().isoformat()

    first_seen = (
        read_json("data/index/financials_first_seen.json") or {}
    )

    whitelists = {}
    results = []

    for cfg in DATASETS:

        st, recs = process(
            cfg,
            whitelists,
            fetch_date,
            now.isoformat(),
            first_seen,
            fetch
        )

        # 公司名單失敗時沿用舊名單
        if (
            cfg["role"] == "company"
            and st["result"] == "failed"
        ):

            old = read_json(
                "data/latest/%s.json" % cfg["name"]
            )

            if old and old.get("records"):

                recs = old["records"]

                st["result"] = "fallback_cached"

                st["note"] = (
                    "本次抓取失敗，沿用上次成功的名單"
                    "（資料日 %s）"
                    % old.get("meta", {}).get("data_date")
                )

        results.append(st)

        if (
            cfg["role"] == "company"
            and recs
            and st["result"] != "failed"
        ):

            whitelists[
                cfg["wlkey"] or cfg["market"]
            ] = {
                code_of(r)
                for r in recs
                if code_of(r)
            }

        time.sleep(SLEEP)

    # 歷史資料範圍檢查
    ranges = []

    for name, market, path, key, code in RANGE_CHECKS:

        ranges.append(
            range_check(
                name,
                market,
                path,
                key,
                code,
                fetch
            )
        )

        time.sleep(SLEEP)

    failed = [
        r for r in results + ranges
        if r["result"] == "failed"
    ]

    status = {
        "run_at": now.isoformat(),
        "fetch_date": fetch_date,
        "failed_count": len(failed),
        "fallback_count": len([
            r for r in results
            if r["result"] == "fallback_cached"
        ]),
        "datasets": results,
        "ranges": ranges,
        "whitelist_sizes": {
            k: len(v)
            for k, v in whitelists.items()
        },
    }

    write_json("data/status.json", status)

    write_json(
        "data/index/financials_first_seen.json",
        first_seen
    )

    print(
        json.dumps(
            {
                "failed": [
                    (r["name"], r.get("error"))
                    for r in failed
                ],
                "fallback": [
                    (
                        r["name"],
                        r.get("note")
                    )
                    for r in results
                    if r["result"] == "fallback_cached"
                ],
                "unavailable": [
                    (
                        r["name"],
                        r.get("note")
                    )
                    for r in results
                    if r["result"] == "unavailable_optional"
                ],
                "ok": sum(
                    r["result"] in ("ok", "unchanged")
                    for r in results + ranges
                ),
            },
            ensure_ascii=False
        )
    )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
