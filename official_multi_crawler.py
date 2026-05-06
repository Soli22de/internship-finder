import json
import hashlib
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import requests
from config import CRAWLER_CONFIG
from parsers.company_registry import get_adapter
from playwright.sync_api import sync_playwright


OUTPUT_FILE = r"c:\jz_code\internship_finding\official_jobs_raw.csv"
SNAPSHOT_LATEST = r"c:\jz_code\internship_finding\snapshot_latest.json"
SNAPSHOT_PREV = r"c:\jz_code\internship_finding\snapshot_prev.json"
HISTORY_DIR = r"c:\jz_code\internship_finding\archive\history\legacy_runs"
HEADLESS = os.getenv("HEADLESS", "1") == "1"
MAX_SCROLL = int(os.getenv("MAX_SCROLL", "10"))
CITY_KEYWORD = os.getenv("CITY_KEYWORD", "上海")
GRAD_KEYWORDS = [x.strip() for x in os.getenv("GRAD_KEYWORDS", "27届,2027届,2027").split(",") if x.strip()]
ENABLED_COMPANIES = set(CRAWLER_CONFIG.get("enabled_companies") or [])
STRICT_MODE_CONFIG = CRAWLER_CONFIG.get("strict_mode") or {}
REQUEST_DELAY_SECONDS = float(CRAWLER_CONFIG.get("request_delay_seconds", 0))
UNKNOWN_PUBLISH_TIME = "不知道发布时间"
UNKNOWN_DEADLINE = "未知截止时间"

SOURCES = [
    {"company": "字节跳动", "source": "official_bytedance", "url_template": "https://jobs.bytedance.com/campus/position?current={page}&limit=40", "pages": 60},
    {"company": "小红书", "source": "official_xiaohongshu", "url_template": "https://job.xiaohongshu.com/campus/position?pageNo={page}", "pages": 120},
    {"company": "快手", "source": "official_kuaishou", "url_template": "https://campus.kuaishou.cn/recruit/campus/e/#/campus", "pages": 1},
    {"company": "腾讯", "source": "official_tencent", "url_template": "https://join.qq.com/campus.html", "pages": 1},
    {"company": "阿里", "source": "official_alibaba", "url_template": "https://talent.alibaba.com/campus/position-list", "pages": 1},
    {"company": "京东", "source": "official_jd", "url_template": "https://campus.jd.com/#/jobs", "pages": 1},
    {"company": "哔哩哔哩", "source": "official_bilibili", "url_template": "https://jobs.bilibili.com/campus", "pages": 1},
    {"company": "美团", "source": "official_meituan", "url_template": "https://zhaopin.meituan.com/web/campus", "pages": 1},
    {"company": "百度", "source": "official_baidu", "url_template": "https://talent.baidu.com/jobs/list?recruitType=2", "pages": 1},
]


def norm(x: Any) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def normalize_time_value(x: Any) -> str:
    v = norm(x)
    if not v:
        return ""
    if re.fullmatch(r"\d{13}", v):
        try:
            return datetime.fromtimestamp(int(v) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return v
    if re.fullmatch(r"\d{10}", v):
        try:
            return datetime.fromtimestamp(int(v)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return v
    return v


def infer_deadline_from_text(text: str) -> str:
    t = norm(text)
    if not t:
        return ""
    m = re.search(r"(截止|截止时间|网申截止|投递截止)[^\d]{0,8}((20\d{2}[./-]\d{1,2}[./-]\d{1,2})(?:\s*\d{1,2}:\d{2})?)", t)
    if m:
        return norm(m.group(2)).replace("/", "-").replace(".", "-")
    return ""


def is_time_like(value: str) -> bool:
    v = norm(value)
    if not v:
        return False
    return bool(re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}|20\d{2}-\d{2}-\d{2})", v))


def source_key(source_name: str) -> str:
    s = norm(source_name).lower()
    return s.replace("official_", "").replace("_api", "")


def is_enabled(source_name: str) -> bool:
    if not ENABLED_COMPANIES:
        return True
    return source_key(source_name) in ENABLED_COMPANIES


def is_strict_mode(source_name: str) -> bool:
    key = source_key(source_name)
    return bool(STRICT_MODE_CONFIG.get(key, False))


def md5_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_external_job_id(row: Dict[str, Any]) -> str:
    ext = norm(row.get("external_job_id"))
    if ext:
        return ext
    seed = f"{norm(row.get('company'))}|{norm(row.get('name'))}|{norm(row.get('city'))}|{norm(row.get('url'))}"
    return md5_text(seed)


def build_content_hash(row: Dict[str, Any]) -> str:
    seed = f"{norm(row.get('name'))}|{norm(row.get('city'))}|{norm(row.get('jd_raw'))}|{norm(row.get('recruit_type'))}"
    return md5_text(seed)


def load_snapshot(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def save_snapshot(path: str, records: List[Dict[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from walk(x)


def get_str(d: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        if k in d and d[k] is not None:
            return norm(d[k])
        for dk, dv in d.items():
            if dk.lower() == k.lower() and dv is not None:
                return norm(dv)
    return ""


def get_city(d: Dict[str, Any]) -> str:
    c = get_str(d, ["city", "work_city", "workCity", "location", "job_city", "city_name", "workplace", "workLocationName"])
    if c:
        return c
    for k in ["city_info", "cityInfo"]:
        val = d.get(k)
        if isinstance(val, dict):
            n = norm(val.get("name") or val.get("i18n_name") or val.get("en_name"))
            if n:
                return n
    txt = norm(
        f"{get_str(d, ['description', 'positionDemand', 'requirement', 'jd'])} "
        f"{get_str(d, ['workLocationName', 'work_location_name'])}"
    )
    if "上海" in txt:
        return "上海"
    return ""


def score_job_like(d: Dict[str, Any]) -> int:
    keys = set(x.lower() for x in d.keys())
    s = 0
    for k in ["title", "name", "positionname", "description", "duty", "requirement", "qualification", "positiondemand", "city", "location", "job_name", "post_url", "url", "id"]:
        if k in keys:
            s += 1
    return s


def is_valid_job_row(title: str, desc: str, req: str) -> bool:
    t = norm(title)
    d = norm(desc)
    r = norm(req)
    if len(t) < 2:
        return False
    if t in {"全部职位", "查看更多", "职位详情", "校招职位"}:
        return False
    if len(d) + len(r) < 20:
        return False
    if re.search(r"(登录|隐私|协议|关于我们|帮助中心|copyright)", t, re.I):
        return False
    return True


def extract_rows_from_payload(payload: Any, source: str, company: str, location_map: Dict[str, str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for d in walk(payload):
        if not isinstance(d, dict):
            continue
        if score_job_like(d) < 3:
            continue
        title = get_str(d, ["title", "name", "positionName", "job_name", "position_name", "jobTitle"])
        desc = get_str(d, ["description", "duty", "jd", "job_desc", "responsibility", "positionDesc"])
        req = get_str(d, ["requirement", "qualification", "job_require", "qualifications", "positionDemand", "position_demand"])
        city = get_city(d)
        rid = get_str(d, ["id", "job_id", "post_id", "position_id", "positionId", "code"])
        work_location_code = get_str(d, ["workLocationCode", "work_location_code", "locationCode"])
        if not city and work_location_code and work_location_code in location_map:
            city = location_map.get(work_location_code, "")
        url = get_str(d, ["url", "post_url", "detail_url", "job_url", "link"])
        if not url and rid:
            if "bytedance" in source:
                url = f"https://jobs.bytedance.com/campus/position/{rid}/detail"
            if "xiaohongshu" in source:
                url = f"https://job.xiaohongshu.com/campus/position?jobId={rid}"
            if "kuaishou" in source:
                url = f"https://campus.kuaishou.cn/recruit/campus/e/#/position/{rid}"
        recruit_type = get_str(d, ["recruit_type", "job_type", "type"])
        if not is_valid_job_row(title, desc, req):
            continue
        raw_publish = normalize_time_value(get_str(d, ["publish_time", "publishTime", "create_time"]))
        raw_deadline = normalize_time_value(get_str(d, ["deadline", "end_time", "expire_time"]))
        publish_time = raw_publish if is_time_like(raw_publish) else UNKNOWN_PUBLISH_TIME
        deadline = raw_deadline if is_time_like(raw_deadline) else UNKNOWN_DEADLINE
        rows.append(
            {
                "url": url,
                "company": company,
                "name": title,
                "city": city,
                "jd_raw": norm(f"{desc} 岗位要求：{req}"),
                "salary": "",
                "company_size": "",
                "duration": "",
                "academic": "",
                "publish_time": publish_time,
                "deadline": deadline,
                "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": source,
                "recruit_type": recruit_type,
                "publish_time_source": "real_api" if publish_time != UNKNOWN_PUBLISH_TIME else "unknown",
                "deadline_source": "real_api" if deadline != UNKNOWN_DEADLINE else "unknown",
            }
        )
    return rows


def crawl_one_source(playwright, conf: Dict[str, Any], use_cdp: bool = False) -> List[Dict[str, str]]:
    if use_cdp:
        browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()
    else:
        browser = playwright.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = context.new_page()
    payloads: List[Any] = []
    api_tasks: List[Dict[str, Any]] = []
    location_map: Dict[str, str] = {}

    def on_response(resp):
        try:
            ct = resp.headers.get("content-type", "")
            if "application/json" not in ct:
                return
            data = resp.json()
            payloads.append(data)

            if "job.xiaohongshu.com/websiterecruit/position/pageQueryPosition" in resp.url:
                req = resp.request
                body = req.post_data
                if body:
                    try:
                        payload = json.loads(body)
                    except Exception:
                        payload = None
                    if isinstance(payload, dict):
                        total = 80
                        page_info = data.get("result") or data.get("data") or {}
                        if isinstance(page_info, dict):
                            total = int(page_info.get("pages") or page_info.get("totalPage") or total)
                        api_tasks.append({"url": resp.url, "payload": payload, "total": min(total, 200), "page_field": "pageNum"})

            if "campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple" in resp.url:
                req = resp.request
                body = req.post_data
                if body:
                    try:
                        payload = json.loads(body)
                    except Exception:
                        payload = None
                    if isinstance(payload, dict):
                        total = int((data.get("result") or {}).get("pages") or 1)
                        api_tasks.append({"url": resp.url, "payload": payload, "total": min(total, 120), "page_field": "pageNum"})

            if "campus.kuaishou.cn/recruit/campus/e/api/v1/open/dictionary/batch" in resp.url:
                result = data.get("result") or {}
                for key in ["workLocation", "work_location", "workLocationCode"]:
                    arr = result.get(key)
                    if isinstance(arr, list):
                        for it in arr:
                            if isinstance(it, dict):
                                code = norm(it.get("code") or it.get("value") or it.get("id"))
                                name = norm(it.get("name") or it.get("label"))
                                if code and name:
                                    location_map[code] = name
        except Exception:
            return

    page.on("response", on_response)
    for p in range(1, conf["pages"] + 1):
        url = conf["url_template"].format(page=p)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            if conf["source"] == "official_kuaishou":
                for tab in ["实习招聘", "应届招聘"]:
                    try:
                        page.get_by_text(tab).first.click(timeout=3000)
                        page.wait_for_timeout(1200)
                    except Exception:
                        pass
            for _ in range(MAX_SCROLL):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(250)
        except Exception:
            continue
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

    seen_api = set()
    for t in api_tasks:
        key = (t["url"], t["page_field"])
        if key in seen_api:
            continue
        seen_api.add(key)
        payload = dict(t["payload"])
        for page_no in range(2, int(t["total"]) + 1):
            payload[t["page_field"]] = page_no
            try:
                resp = context.request.post(
                    t["url"],
                    data=json.dumps(payload),
                    headers={"content-type": "application/json"},
                    timeout=30000,
                )
                if resp.ok:
                    payloads.append(resp.json())
            except Exception:
                continue

    rows: List[Dict[str, str]] = []
    for payload in payloads:
        rows.extend(extract_rows_from_payload(payload, conf["source"], conf["company"], location_map))

    seen = set()
    out = []
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["url"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    try:
        page.close()
    except Exception:
        pass
    if not use_cdp:
        try:
            context.close()
            browser.close()
        except Exception:
            pass
    # In CDP mode do NOT close context/browser to keep manual session alive
    return out


def fetch_jd_jobs() -> List[Dict[str, str]]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://campus.jd.com/#/jobs",
        "Content-Type": "application/json",
    }
    list_url = "https://campus.jd.com/api/wx/position/page?type=present"
    rows: List[Dict[str, str]] = []
    page_size = 50
    page_index = 0
    total_pages = 1
    while page_index < total_pages:
        payload = {
            "pageSize": page_size,
            "pageIndex": page_index,
            "parameter": {
                "positionName": "",
                "planIdList": [],
                "jobDirectionCodeList": [],
                "workCityCodeList": [],
                "positionDeptList": [],
            },
        }
        try:
            data = requests.post(list_url, json=payload, headers=headers, timeout=30).json()
        except Exception:
            break
        body = data.get("body") or {}
        items = body.get("items") or []
        total_number = int(body.get("totalNumber") or 0)
        total_pages = max(1, (total_number + page_size - 1) // page_size)

        for it in items:
            title = norm(it.get("positionName"))
            city = norm(it.get("workCity"))
            publish_id = norm(it.get("publishId"))
            req_id = norm(it.get("reqId"))
            city_set = []
            req_list = it.get("requirementVoList") or []
            if isinstance(req_list, list):
                for req in req_list:
                    if isinstance(req, dict):
                        wc = norm(req.get("workCity"))
                        if wc and wc not in city_set:
                            city_set.append(wc)
            if city_set:
                city = " ".join(city_set)
            work_content = norm(it.get("workContent"))
            qualification = norm(it.get("qualification"))
            if not title:
                continue
            rows.append(
                {
                    "url": f"https://campus.jd.com/home#/newDetails?publishId={publish_id}&reqId={req_id}" if publish_id else "https://campus.jd.com/home#/jobs",
                    "company": "京东",
                    "name": title,
                    "city": city,
                    "jd_raw": norm(f"{work_content} 岗位要求：{qualification}"),
                    "salary": "",
                    "company_size": "",
                    "duration": "",
                    "academic": norm(it.get("education")),
                    "publish_time": normalize_time_value(it.get("publishTime")),
                    "deadline": "",
                    "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "official_jd_api",
                    "recruit_type": "应届生",
                }
            )
        page_index += 1
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

    dedup = []
    seen = set()
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def fetch_tencent_jobs(max_pages: int = 120) -> List[Dict[str, str]]:
    adapter = get_adapter("tencent")
    if adapter is None:
        return []

    items: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        try:
            page_items = adapter.fetch_list(page) or []
        except Exception:
            page_items = []
        if not page_items:
            break
        items.extend(page_items)
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

    rows: List[Dict[str, str]] = []
    for it in items:
        parsed = adapter.parse(it)
        if not parsed.get("title"):
            continue
        collect_ts = parsed.get("collect_time", time.strftime("%Y-%m-%d %H:%M:%S"))
        raw_publish = normalize_time_value(parsed.get("publish_time"))
        update_proxy = normalize_time_value(parsed.get("update_time"))
        if is_time_like(raw_publish):
            publish_time = raw_publish
            publish_source = "real_api"
        elif is_time_like(update_proxy):
            publish_time = update_proxy
            publish_source = "official_update_proxy"
        else:
            publish_time = UNKNOWN_PUBLISH_TIME
            publish_source = "unknown"
        raw_deadline = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
        if is_time_like(raw_deadline):
            deadline = raw_deadline
            deadline_source = "real_api_or_text"
        else:
            deadline = UNKNOWN_DEADLINE
            deadline_source = "unknown"
        rows.append(
            {
                "url": parsed.get("url", ""),
                "company": parsed.get("company", "腾讯"),
                "name": parsed.get("title", ""),
                "city": parsed.get("city", ""),
                "jd_raw": parsed.get("jd_raw", ""),
                "salary": "",
                "company_size": "",
                "duration": "",
                "academic": "",
                "publish_time": publish_time,
                "deadline": deadline,
                "collect_time": collect_ts,
                "source": parsed.get("source", "official_tencent_api"),
                "recruit_type": parsed.get("recruit_type", ""),
                "raw_tags": parsed.get("raw_tags", ""),
                "external_job_id": parsed.get("external_job_id", ""),
                "update_time": normalize_time_value(parsed.get("update_time", "")),
                "publish_time_source": publish_source,
                "deadline_source": deadline_source,
            }
        )
    dedup = []
    seen = set()
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["external_job_id"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def fetch_kuaishou_jobs_api(max_pages: int = 120) -> List[Dict[str, str]]:
    adapter = get_adapter("kuaishou")
    if adapter is None:
        return []

    items: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        try:
            page_items = adapter.fetch_list(page) or []
        except Exception:
            page_items = []
        if not page_items:
            break
        items.extend(page_items)
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

    rows: List[Dict[str, str]] = []
    for it in items:
        parsed = adapter.parse(it)
        if not parsed.get("title"):
            continue

        collect_ts = parsed.get("collect_time", time.strftime("%Y-%m-%d %H:%M:%S"))
        raw_publish = normalize_time_value(parsed.get("publish_time"))
        update_proxy = normalize_time_value(parsed.get("update_time"))
        if is_time_like(raw_publish):
            publish_time = raw_publish
            publish_source = "real_api"
        elif is_time_like(update_proxy):
            publish_time = update_proxy
            publish_source = "official_update_proxy"
        else:
            publish_time = UNKNOWN_PUBLISH_TIME
            publish_source = "unknown"
        raw_deadline = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
        if is_time_like(raw_deadline):
            deadline = raw_deadline
            deadline_source = "real_api_or_text"
        else:
            deadline = UNKNOWN_DEADLINE
            deadline_source = "unknown"
        rows.append(
            {
                "url": parsed.get("url", ""),
                "company": parsed.get("company", "快手"),
                "name": parsed.get("title", ""),
                "city": parsed.get("city", ""),
                "jd_raw": parsed.get("jd_raw", ""),
                "salary": "",
                "company_size": "",
                "duration": "",
                "academic": "",
                "publish_time": publish_time,
                "deadline": deadline,
                "collect_time": collect_ts,
                "source": parsed.get("source", "official_kuaishou_api"),
                "recruit_type": parsed.get("recruit_type", ""),
                "raw_tags": parsed.get("raw_tags", ""),
                "external_job_id": parsed.get("external_job_id", ""),
                "update_time": normalize_time_value(parsed.get("update_time", "")),
                "publish_time_source": publish_source,
                "deadline_source": deadline_source,
            }
        )
    dedup = []
    seen = set()
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["url"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def fetch_xiaohongshu_jobs_api(max_pages: int = 120) -> List[Dict[str, str]]:
    adapter = get_adapter("xiaohongshu")
    if adapter is None:
        return []

    items: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        try:
            page_items = adapter.fetch_list(page) or []
        except Exception:
            page_items = []
        if not page_items:
            break
        items.extend(page_items)
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

    rows: List[Dict[str, str]] = []
    for it in items:
        parsed = adapter.parse(it)
        if not parsed.get("title"):
            continue

        collect_ts = parsed.get("collect_time", time.strftime("%Y-%m-%d %H:%M:%S"))
        raw_publish = normalize_time_value(parsed.get("publish_time") or parsed.get("update_time"))
        publish_time = raw_publish if is_time_like(raw_publish) else UNKNOWN_PUBLISH_TIME
        publish_source = "real_api" if publish_time != UNKNOWN_PUBLISH_TIME else "unknown"
        raw_deadline = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
        deadline = raw_deadline if is_time_like(raw_deadline) else UNKNOWN_DEADLINE
        deadline_source = "real_api_or_text" if deadline != UNKNOWN_DEADLINE else "unknown"
        rows.append(
            {
                "url": parsed.get("url", ""),
                "company": parsed.get("company", "小红书"),
                "name": parsed.get("title", ""),
                "city": parsed.get("city", ""),
                "jd_raw": parsed.get("jd_raw", ""),
                "salary": "",
                "company_size": "",
                "duration": "",
                "academic": "",
                "publish_time": publish_time,
                "deadline": deadline,
                "collect_time": collect_ts,
                "source": parsed.get("source", "official_xiaohongshu"),
                "recruit_type": parsed.get("recruit_type", ""),
                "raw_tags": parsed.get("raw_tags", ""),
                "external_job_id": parsed.get("external_job_id", ""),
                "update_time": normalize_time_value(parsed.get("update_time", "")),
                "publish_time_source": publish_source,
                "deadline_source": deadline_source,
            }
        )
    dedup = []
    seen = set()
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["url"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def fetch_meituan_jobs_api(max_pages: int = 150) -> List[Dict[str, str]]:
    adapter = get_adapter("meituan")
    if adapter is None:
        return []
    rows: List[Dict[str, str]] = []
    for page in range(1, max_pages + 1):
        try:
            items = adapter.fetch_list(page)
        except Exception:
            items = []
        if not items:
            break
        for it in items:
            parsed = adapter.parse(it)
            if not parsed.get("title"):
                continue
            detail = {}
            try:
                detail = adapter.fetch_detail(parsed.get("external_job_id", ""))
            except Exception:
                detail = {}
            if detail:
                detail_desc = normalize_text(detail.get("positionDescription"))
                detail_req = normalize_text(detail.get("positionRequire"))
                current_jd = normalize_text(parsed.get("jd_raw", ""))
                if len(current_jd) < 30 or ("岗位要求：" in current_jd and len(current_jd.split("岗位要求：")[-1].strip()) < 8):
                    parsed["jd_raw"] = normalize_text(f"{detail_desc} 岗位要求：{detail_req}")
                if not normalize_time_value(parsed.get("publish_time")):
                    parsed["publish_time"] = normalize_time_value(detail.get("pushTime"))
                if not normalize_time_value(parsed.get("deadline")):
                    parsed["deadline"] = normalize_time_value(detail.get("webApplyEndTime"))
                if not normalize_time_value(parsed.get("update_time")):
                    parsed["update_time"] = normalize_time_value(detail.get("pushTime"))
            collect_ts = parsed.get("collect_time", time.strftime("%Y-%m-%d %H:%M:%S"))
            raw_publish = normalize_time_value(parsed.get("publish_time"))
            update_proxy = normalize_time_value(parsed.get("update_time"))
            if is_time_like(raw_publish):
                publish_time = raw_publish
                publish_source = "real_api"
            elif is_time_like(update_proxy):
                publish_time = update_proxy
                publish_source = "official_update_proxy"
            else:
                publish_time = UNKNOWN_PUBLISH_TIME
                publish_source = "unknown"
            raw_deadline = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
            if is_time_like(raw_deadline):
                deadline = raw_deadline
                deadline_source = "real_api_or_text"
            else:
                deadline = UNKNOWN_DEADLINE
                deadline_source = "unknown"
            rows.append(
                {
                    "url": parsed.get("url", ""),
                    "company": parsed.get("company", "美团"),
                    "name": parsed.get("title", ""),
                    "city": parsed.get("city", ""),
                    "jd_raw": parsed.get("jd_raw", ""),
                    "salary": "",
                    "company_size": "",
                    "duration": "",
                    "academic": "",
                    "publish_time": publish_time,
                    "deadline": deadline,
                    "collect_time": collect_ts,
                    "source": parsed.get("source", "official_meituan"),
                    "recruit_type": parsed.get("recruit_type", ""),
                    "raw_tags": parsed.get("raw_tags", ""),
                    "external_job_id": parsed.get("external_job_id", ""),
                    "update_time": normalize_time_value(parsed.get("update_time", "")),
                    "publish_time_source": publish_source,
                    "deadline_source": deadline_source,
                }
            )
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
    dedup = []
    seen = set()
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["external_job_id"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def fetch_alibaba_jobs_api(max_pages: int = 120) -> List[Dict[str, str]]:
    adapter = get_adapter("alibaba")
    if adapter is None:
        return []
    rows: List[Dict[str, str]] = []
    for page in range(1, max_pages + 1):
        try:
            items = adapter.fetch_list(page)
        except Exception:
            items = []
        if not items:
            break
        for it in items:
            parsed = adapter.parse(it)
            if not parsed.get("title"):
                continue
            collect_ts = parsed.get("collect_time", time.strftime("%Y-%m-%d %H:%M:%S"))
            raw_publish = normalize_time_value(parsed.get("publish_time"))
            update_proxy = normalize_time_value(parsed.get("update_time"))
            if is_time_like(raw_publish):
                publish_time = raw_publish
                publish_source = "real_api"
            elif is_time_like(update_proxy):
                publish_time = update_proxy
                publish_source = "official_update_proxy"
            else:
                publish_time = UNKNOWN_PUBLISH_TIME
                publish_source = "unknown"
            raw_deadline = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
            if is_time_like(raw_deadline):
                deadline = raw_deadline
                deadline_source = "real_api_or_text"
            else:
                deadline = UNKNOWN_DEADLINE
                deadline_source = "unknown"
            rows.append(
                {
                    "url": parsed.get("url", ""),
                    "company": parsed.get("company", "阿里"),
                    "name": parsed.get("title", ""),
                    "city": parsed.get("city", ""),
                    "jd_raw": parsed.get("jd_raw", ""),
                    "salary": "",
                    "company_size": "",
                    "duration": "",
                    "academic": "",
                    "publish_time": publish_time,
                    "deadline": deadline,
                    "collect_time": collect_ts,
                    "source": parsed.get("source", "official_alibaba"),
                    "recruit_type": parsed.get("recruit_type", ""),
                    "raw_tags": parsed.get("raw_tags", ""),
                    "external_job_id": parsed.get("external_job_id", ""),
                    "update_time": normalize_time_value(parsed.get("update_time", "")),
                    "publish_time_source": publish_source,
                    "deadline_source": deadline_source,
                }
            )
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
    dedup = []
    seen = set()
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["external_job_id"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def fetch_bilibili_jobs_api(max_pages: int = 120) -> List[Dict[str, str]]:
    adapter = get_adapter("bilibili")
    if adapter is None:
        return []
    if hasattr(adapter, "set_mode"):
        adapter.set_mode(is_strict_mode("official_bilibili"))

    items: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        try:
            page_items = adapter.fetch_list(page) or []
        except Exception:
            page_items = []
        if not page_items:
            break
        items.extend(page_items)
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

    rows: List[Dict[str, str]] = []
    for it in items:
        parsed = adapter.parse(it)
        if not parsed.get("title"):
            continue
        collect_ts = parsed.get("collect_time", time.strftime("%Y-%m-%d %H:%M:%S"))
        raw_publish = normalize_time_value(parsed.get("publish_time") or parsed.get("update_time"))
        publish_time = raw_publish if is_time_like(raw_publish) else UNKNOWN_PUBLISH_TIME
        publish_source = "real_api" if publish_time != UNKNOWN_PUBLISH_TIME else "unknown"
        raw_deadline = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
        deadline = raw_deadline if is_time_like(raw_deadline) else UNKNOWN_DEADLINE
        deadline_source = "real_api_or_text" if deadline != UNKNOWN_DEADLINE else "unknown"
        rows.append(
            {
                "url": parsed.get("url", ""),
                "company": parsed.get("company", "哔哩哔哩"),
                "name": parsed.get("title", ""),
                "city": parsed.get("city", ""),
                "jd_raw": parsed.get("jd_raw", ""),
                "salary": "",
                "company_size": "",
                "duration": "",
                "academic": "",
                "publish_time": publish_time,
                "deadline": deadline,
                "collect_time": collect_ts,
                "source": parsed.get("source", "official_bilibili"),
                "recruit_type": parsed.get("recruit_type", ""),
                "raw_tags": parsed.get("raw_tags", ""),
                "external_job_id": parsed.get("external_job_id", ""),
                "update_time": normalize_time_value(parsed.get("update_time", "")),
                "publish_time_source": publish_source,
                "deadline_source": deadline_source,
            }
        )
    dedup = []
    seen = set()
    for r in rows:
        key = (r["company"], r["name"], r["city"], r["external_job_id"], r["jd_raw"][:200])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def build_source_param_audit() -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    try:
        s = requests.Session()
        base_headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://jobs.bilibili.com/campus/positions",
            "Origin": "https://jobs.bilibili.com",
            "X-AppKey": "ops.ehr-api.auth",
            "X-UserType": "2",
            "Content-Type": "application/json",
        }
        s.get("https://jobs.bilibili.com/campus/positions", headers=base_headers, timeout=20)
        token = (s.get("https://jobs.bilibili.com/api/auth/v1/csrf/token", headers=base_headers, timeout=20).json() or {}).get("data")
        headers = dict(base_headers)
        headers["X-CSRF"] = norm(token)
        bilibili_payloads = [
            (
                "bilibili_strict",
                {
                    "pageSize": 30,
                    "pageNum": 1,
                    "positionName": "",
                    "postCode": [],
                    "postCodeList": [],
                    "workLocationList": [],
                    "workTypeList": ["3"],
                    "positionTypeList": ["3"],
                    "deptCodeList": [],
                    "recruitType": None,
                    "practiceTypes": [],
                    "onlyHotRecruit": 0,
                },
            ),
            ("bilibili_relaxed", {"pageSize": 30, "pageNum": 1, "recruitType": 1}),
            ("bilibili_full", {"pageSize": 30, "pageNum": 1}),
        ]
        for strategy, payload in bilibili_payloads:
            try:
                resp = s.post("https://jobs.bilibili.com/api/campus/position/positionList", json=payload, headers=headers, timeout=30).json()
                data = resp.get("data") or {}
                items = data.get("list") or []
                rows.append(
                    {
                        "company": "哔哩哔哩",
                        "source": "official_bilibili",
                        "strategy": strategy,
                        "total": int(data.get("total") or len(items)),
                        "pages": int(data.get("pages") or 0),
                        "list_len_page1": len(items),
                        "status": "ok" if int(resp.get("code", -1)) == 0 else "failed",
                        "message": norm(resp.get("message")),
                    }
                )
            except Exception as e:
                rows.append(
                    {
                        "company": "哔哩哔哩",
                        "source": "official_bilibili",
                        "strategy": strategy,
                        "total": 0,
                        "pages": 0,
                        "list_len_page1": 0,
                        "status": "failed",
                        "message": norm(str(e)),
                    }
                )
    except Exception as e:
        rows.append(
            {
                "company": "哔哩哔哩",
                "source": "official_bilibili",
                "strategy": "audit_init",
                "total": 0,
                "pages": 0,
                "list_len_page1": 0,
                "status": "failed",
                "message": norm(str(e)),
            }
        )
    return pd.DataFrame(rows)


def main():
    if os.getenv("USE_SPLIT_CRAWLERS", "1") == "1":
        from crawlers.run_all_official import main as run_all_official_main

        run_all_official_main()
        return
    all_rows: List[Dict[str, str]] = []
    fetch_health_rows: List[Dict[str, Any]] = []
    with sync_playwright() as p:
        for conf in SOURCES:
            if not is_enabled(conf["source"]):
                continue
            if conf["source"] in {"official_kuaishou", "official_xiaohongshu", "official_meituan", "official_alibaba", "official_tencent", "official_jd", "official_bilibili"}:
                continue
            rows = crawl_one_source(p, conf)
            print(conf["company"], conf["source"], len(rows))
            all_rows.extend(rows)
            fetch_health_rows.append({"company": conf["company"], "source": conf["source"], "rows": len(rows), "status": "ok", "strict_mode": is_strict_mode(conf["source"])})

    if is_enabled("official_tencent_api"):
        tencent_rows = fetch_tencent_jobs()
        print("腾讯 official_tencent_api", len(tencent_rows))
        all_rows.extend(tencent_rows)
        fetch_health_rows.append({"company": "腾讯", "source": "official_tencent_api", "rows": len(tencent_rows), "status": "ok", "strict_mode": is_strict_mode("official_tencent_api")})

    if is_enabled("official_kuaishou_api"):
        kuaishou_rows = fetch_kuaishou_jobs_api()
        print("快手 official_kuaishou_api", len(kuaishou_rows))
        all_rows.extend(kuaishou_rows)
        fetch_health_rows.append({"company": "快手", "source": "official_kuaishou_api", "rows": len(kuaishou_rows), "status": "ok", "strict_mode": is_strict_mode("official_kuaishou_api")})

    if is_enabled("official_xiaohongshu"):
        xiaohongshu_rows = fetch_xiaohongshu_jobs_api()
        print("小红书 official_xiaohongshu", len(xiaohongshu_rows))
        all_rows.extend(xiaohongshu_rows)
        fetch_health_rows.append({"company": "小红书", "source": "official_xiaohongshu", "rows": len(xiaohongshu_rows), "status": "ok", "strict_mode": is_strict_mode("official_xiaohongshu")})

    if is_enabled("official_meituan"):
        meituan_rows = fetch_meituan_jobs_api()
        print("美团 official_meituan", len(meituan_rows))
        all_rows.extend(meituan_rows)
        fetch_health_rows.append({"company": "美团", "source": "official_meituan", "rows": len(meituan_rows), "status": "ok", "strict_mode": is_strict_mode("official_meituan")})

    if is_enabled("official_alibaba"):
        alibaba_rows = fetch_alibaba_jobs_api()
        print("阿里 official_alibaba", len(alibaba_rows))
        all_rows.extend(alibaba_rows)
        fetch_health_rows.append({"company": "阿里", "source": "official_alibaba", "rows": len(alibaba_rows), "status": "ok", "strict_mode": is_strict_mode("official_alibaba")})

    if is_enabled("official_jd_api"):
        jd_rows = fetch_jd_jobs()
        print("京东 official_jd_api", len(jd_rows))
        all_rows.extend(jd_rows)
        fetch_health_rows.append({"company": "京东", "source": "official_jd_api", "rows": len(jd_rows), "status": "ok", "strict_mode": is_strict_mode("official_jd_api")})

    if is_enabled("official_bilibili"):
        bilibili_rows = fetch_bilibili_jobs_api()
        print("哔哩哔哩 official_bilibili", len(bilibili_rows))
        all_rows.extend(bilibili_rows)
        fetch_health_rows.append({"company": "哔哩哔哩", "source": "official_bilibili", "rows": len(bilibili_rows), "status": "ok", "strict_mode": is_strict_mode("official_bilibili")})

    if not all_rows:
        print("官方站未抓到可用数据")
        return

    df = pd.DataFrame(all_rows)
    df = df.fillna("")
    df["external_job_id"] = df.apply(lambda r: build_external_job_id(r.to_dict()), axis=1)
    df["content_hash"] = df.apply(lambda r: build_content_hash(r.to_dict()), axis=1)
    df["sync_key"] = df["source"].map(norm) + "|" + df["external_job_id"].map(norm)
    df = df.drop_duplicates(subset=["company", "name", "city", "url", "jd_raw"], keep="first")

    if os.path.exists(SNAPSHOT_LATEST):
        try:
            if os.path.exists(SNAPSHOT_PREV):
                os.remove(SNAPSHOT_PREV)
            os.replace(SNAPSHOT_LATEST, SNAPSHOT_PREV)
        except Exception:
            pass

    prev_records = load_snapshot(SNAPSHOT_PREV)
    prev_map = {f"{norm(r.get('source'))}|{norm(r.get('external_job_id'))}": r for r in prev_records}

    status_list = []
    change_rows = []
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    first_seen_list = []
    for row in df.to_dict(orient="records"):
        key = row["sync_key"]
        new_hash = norm(row["content_hash"])
        old_record = prev_map.get(key)
        old_hash = norm((old_record or {}).get("content_hash"))
        if old_record is None:
            status = "NEW"
            first_seen_time = now_ts
        elif old_hash != new_hash:
            status = "UPDATED"
            first_seen_time = norm(old_record.get("first_seen_time")) or now_ts
        else:
            status = "UNCHANGED"
            first_seen_time = norm(old_record.get("first_seen_time")) or now_ts
        status_list.append(status)
        first_seen_list.append(first_seen_time)
        if status in {"NEW", "UPDATED"}:
            change_rows.append({"sync_key": key, "status": status, "collect_time": now_ts})
    df["sync_status"] = status_list
    df["first_seen_time"] = first_seen_list
    df["publish_time_estimated"] = ""
    df["publish_time_estimated_source"] = ""
    unknown_mask = df["publish_time"].astype(str).eq(UNKNOWN_PUBLISH_TIME)
    df.loc[unknown_mask, "publish_time_estimated"] = df.loc[unknown_mask, "first_seen_time"]
    df.loc[unknown_mask, "publish_time_estimated_source"] = "history_first_seen"
    df.loc[~unknown_mask, "publish_time_estimated"] = df.loc[~unknown_mask, "publish_time"]
    df.loc[~unknown_mask, "publish_time_estimated_source"] = df.loc[~unknown_mask, "publish_time_source"]

    current_keys = set(df["sync_key"].tolist())
    for key in prev_map.keys():
        if key not in current_keys:
            change_rows.append({"sync_key": key, "status": "CLOSED", "collect_time": now_ts})

    snapshot_rows = df[["source", "external_job_id", "content_hash", "first_seen_time"]].to_dict(orient="records")
    save_snapshot(SNAPSHOT_LATEST, snapshot_rows)

    os.makedirs(HISTORY_DIR, exist_ok=True)
    reports_dir = os.path.join(os.path.dirname(OUTPUT_FILE), "outputs", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    change_file_json = os.path.join(HISTORY_DIR, f"changes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(change_file_json, "w", encoding="utf-8") as f:
        json.dump(change_rows, f, ensure_ascii=False, indent=2)
    change_file_csv = change_file_json.replace(".json", ".csv")
    pd.DataFrame(change_rows).to_csv(change_file_csv, index=False, encoding="utf-8-sig")

    df = df.drop(columns=["sync_key"])
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    param_audit = build_source_param_audit()
    param_audit.to_csv(os.path.join(reports_dir, "source_param_audit.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(fetch_health_rows).to_csv(os.path.join(reports_dir, "source_fetch_health.csv"), index=False, encoding="utf-8-sig")
    print("official_rows", len(df), OUTPUT_FILE)
    print("changes_file", change_file_json)


if __name__ == "__main__":
    main()
