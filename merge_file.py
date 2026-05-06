import glob
import asyncio
import os
import re
from collections import Counter
from datetime import datetime
from functools import lru_cache

import pandas as pd
from rules.cohort27_rules import classify_27_cohort
from rules.location_normalizer import normalize_city
from utils.link_checker import check_links_batch

shixiseng_path = r"C:\jz_code\internship_finding\archive\history\shixiseng\实习僧公司要求大全"
bytedance_output_path = r"C:\jz_code\internship_finding\real-useful-resume\output"
official_raw_file = r"C:\jz_code\internship_finding\official_jobs_raw.csv"
BASE_DIR = r"C:\jz_code\internship_finding"
OUTPUT_REPORT_DIR = os.path.join(BASE_DIR, "outputs", "reports")
OUTPUT_DASHBOARD_DIR = os.path.join(BASE_DIR, "outputs", "dashboard")
OUTPUT_HEALTH_DIR = os.path.join(BASE_DIR, "outputs", "health")

big_company_keywords = [
    "字节跳动", "阿里", "腾讯", "美团", "京东", "哔哩哔哩", "小红书", "拼多多", "快手", "华为", "米哈游",
    "百度", "网易", "滴滴", "蚂蚁", "携程", "理想", "小米", "科大讯飞", "联想", "荣耀", "顺丰", "Shopee"
]

role_keywords = [
    "数据分析", "商业分析", "策略分析", "经营分析", "bi", "产品经理", "数据产品", "产品运营",
    "增长", "业务分析", "信息化", "数字化", "系统实施", "sql", "python", "ab测试", "实验", "用户增长"
]

grade_keywords = [
    "27届", "2027届", "2027", "2026年9月-2027年8月", "26年9月-27年8月", "2027年毕业", "2027届毕业生",
    "26-27届", "2026-2027", "2026/2027", "27届及以后", "2027届及以后", "27届毕业", "26届-27届",
    "x-star", "xstar", "快star", "kstar", "redstar", "red star", "青锐计划", "北斗计划", "转正实习", "技术大咖", "跃动计划", "产培生", "大咖实习", "青云计划", "新星计划", "bilibili星", "珠峰计划", "新锐之星", "天才计划"
]

skill_keywords = [
    "sql", "python", "excel", "tableau", "power bi", "统计", "机器学习", "a/b", "ab测试",
    "产品思维", "增长", "数据建模", "数据仓库", "hive", "spark", "沟通协作", "项目管理"
]

dashboard_skill_keywords = [
    "python", "sql", "spark", "hadoop", "tableau", "power bi", "hive", "数据分析", "机器学习", "统计"
]
priority_skill_keywords = ["python", "sql", "spark", "hadoop", "hive", "tableau", "power bi", "机器学习", "统计", "数据分析"]
TARGET_CITY = "上海"
TARGET_COMPANIES = ["快手", "腾讯", "字节跳动", "小红书", "美团", "阿里", "京东", "哔哩哔哩", "百度"]
OFFICIAL_PRIORITY_COMPANY_KEYWORDS = ["字节", "腾讯", "快手", "小红书", "美团", "阿里", "京东", "哔哩哔哩", "百度"]
SHANGHAI_VARIANTS = ["上海", "上海市", "浦东", "徐汇", "静安", "杨浦", "闵行", "虹口", "长宁", "普陀", "松江", "嘉定", "青浦", "奉贤", "金山", "崇明", "总部base上海", "base上海", "上海/北京", "上海/深圳", "上海/杭州"]

# 性能优化：全局预编译正则，避免热路径重复编译
RE_SPACES = re.compile(r"\s+")
RE_RESP = re.compile(r"(岗位职责|职位描述|工作职责)[:：]?(.*?)(岗位要求|任职要求|职位要求|加分项|$)")
RE_REQ = re.compile(r"(岗位要求|任职要求|职位要求)[:：]?(.*?)(加分项|工作地点|$)")
RE_DEGREE = re.compile(r"(本科及以上|硕士及以上|博士|本科|硕士|大专及以上|不限学历)")
RE_GRAD_BATCH = re.compile(r"(27届|2027届|2027年毕业|2026年9月-2027年8月)")
RE_INTERN_DAYS = re.compile(r"(每周.*?\d+天|\d+天/周|\d+天以上)")
RE_INTERN_MONTHS = re.compile(r"(\d+个月|实习.*?个月)")
RE_27_PAIR = re.compile(r"(26|2026).{0,8}(27|2027)")
RE_27_AFTER = re.compile(r"(27|2027).{0,8}(及以后|以后)")
RE_CITY_FALLBACK = re.compile(r"^(.{2,30})")
RE_NAME_CLEAN_COMPANY = re.compile(r"公司简介.*")
RE_NAME_CLEAN_LOCATION = re.compile(r"工作地点[:：].*")
RE_NAME_CLEAN_MAP = re.compile(r"收起地图.*")
RE_TIME_YMD = re.compile(r"[年/月.]")
RE_MULTI_DELIMS = re.compile(r"[/、]|全国|多地|异地")
RE_ROLE_ANALYSIS = re.compile(r"(数据分析|商业分析|策略分析|经营分析|bi|tableau|power bi)")
RE_ROLE_ENGINEERING = re.compile(r"(数据开发|数据工程|数仓|数据仓库|hadoop|spark|hive|etl)")
RE_ROLE_ALGO = re.compile(r"(算法|机器学习|推荐|搜索|nlp|cv|深度学习)")
RE_DATA_JOB = re.compile(r"(数据|分析|策略|算法|商业分析|bi|python|sql)")
RE_FALSE_NEG = re.compile(r"2027|27届|暑期实习|留用|转正|2026.9|2027.8")
RE_SALARY_K_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*k")
RE_SALARY_K_PLUS = re.compile(r"(\d+(?:\.\d+)?)\s*k\s*(?:以上|起)")
RE_SALARY_DAY_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*元\s*/?\s*天")
RE_EXP_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*年")
RE_EXP_PLUS = re.compile(r"(\d+(?:\.\d+)?)\s*年\s*(?:以上|及以上)")
RE_EXP_ANY = re.compile(r"(?:经验|工作年限|相关经历)[^0-9]{0,6}(\d+(?:\.\d+)?)\s*年")
RE_EXP_ZERO = re.compile(r"(应届|不限经验|无经验|无需经验|在校生|实习生)")


def ensure_output_dirs():
    os.makedirs(OUTPUT_REPORT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DASHBOARD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_HEALTH_DIR, exist_ok=True)


def report_path(file_name: str) -> str:
    return os.path.join(OUTPUT_REPORT_DIR, file_name)


def dashboard_path(file_name: str) -> str:
    return os.path.join(OUTPUT_DASHBOARD_DIR, file_name)


def health_path(file_name: str) -> str:
    return os.path.join(OUTPUT_HEALTH_DIR, file_name)


# 性能优化：缓存归一化文本，避免同值多次处理
@lru_cache(maxsize=200000)
def _normalize_text_cached(x: str) -> str:
    txt = str(x).replace("\u3000", " ").replace("\xa0", " ")
    return RE_SPACES.sub(" ", txt).strip()


def normalize_text(x):
    if pd.isna(x):
        return ""
    return _normalize_text_cached(str(x))


# 性能优化：向量化归一化，替代逐行 map(normalize_text)
def normalize_text_series(s: pd.Series) -> pd.Series:
    if not isinstance(s, pd.Series):
        s = pd.Series([s] * 0, dtype="string")
    out = s.fillna("").astype("string")
    out = out.str.replace("\u3000", " ", regex=False).str.replace("\xa0", " ", regex=False)
    out = out.str.replace(RE_SPACES, " ", regex=True).str.strip()
    return out.fillna("")


def split_jd(info):
    text = normalize_text(info)
    if not text:
        return "", ""
    resp = ""
    req = ""
    m_resp = RE_RESP.search(text)
    if m_resp:
        resp = normalize_text(m_resp.group(2))
    m_req = RE_REQ.search(text)
    if m_req:
        req = normalize_text(m_req.group(2))
    if resp and not req:
        req = resp
    if not resp and not req:
        req = text
    return resp, req


def extract_degree(text):
    t = normalize_text(text)
    m = RE_DEGREE.search(t)
    return m.group(1) if m else ""


def extract_graduation_batch(text):
    t = normalize_text(text)
    m = RE_GRAD_BATCH.search(t)
    if m:
        return m.group(1)
    return ""


def extract_intern_days(text):
    t = normalize_text(text)
    m = RE_INTERN_DAYS.search(t)
    return m.group(1) if m else ""


def extract_intern_months(text):
    t = normalize_text(text)
    m = RE_INTERN_MONTHS.search(t)
    return m.group(1) if m else ""


def normalize_salary(text):
    t = normalize_text(text).lower()
    if not t:
        return ""
    m = RE_SALARY_K_RANGE.search(t)
    if m:
        low = float(m.group(1))
        high = float(m.group(2))
        if low > high:
            low, high = high, low
        if low.is_integer() and high.is_integer():
            return f"{int(low)}-{int(high)}K/月"
        return f"{round(low, 1)}-{round(high, 1)}K/月"
    m = RE_SALARY_K_PLUS.search(t)
    if m:
        v = float(m.group(1))
        if v.is_integer():
            return f"{int(v)}K+/月"
        return f"{round(v, 1)}K+/月"
    m = RE_SALARY_DAY_RANGE.search(t)
    if m:
        low = float(m.group(1)) * 21.75 / 1000
        high = float(m.group(2)) * 21.75 / 1000
        if low > high:
            low, high = high, low
        return f"{round(low, 1)}-{round(high, 1)}K/月"
    return ""


def normalize_degree(text):
    t = normalize_text(text)
    if not t:
        return ""
    if re.search(r"(博士)", t):
        return "博士"
    if re.search(r"(硕士及以上|硕士|研究生)", t):
        return "硕士"
    if re.search(r"(本科及以上|本科)", t):
        return "本科"
    if re.search(r"(大专及以上|大专)", t):
        return "大专"
    if re.search(r"(不限学历|学历不限)", t):
        return "不限"
    return "其他"


def normalize_years_experience(text):
    t = normalize_text(text)
    if not t:
        return ""
    m = RE_EXP_RANGE.search(t)
    if m:
        low = int(float(m.group(1)))
        high = int(float(m.group(2)))
        if low > high:
            low, high = high, low
        return f"{low}-{high}年"
    m = RE_EXP_PLUS.search(t)
    if m:
        return f"{int(float(m.group(1)))}年+"
    m = RE_EXP_ANY.search(t)
    if m:
        return f"{int(float(m.group(1)))}年"
    if RE_EXP_ZERO.search(t):
        return "0年"
    return ""


def vectorized_normalize_salary(text_s: pd.Series) -> pd.Series:
    # 性能优化：薪资标准化向量化，替代逐行 map(normalize_salary)
    t = text_s.fillna("").astype("string").str.lower()
    out = pd.Series("", index=t.index, dtype="string")
    m1 = t.str.extract(RE_SALARY_K_RANGE, expand=True)
    has_m1 = m1[0].notna() & m1[1].notna()
    if has_m1.any():
        low = pd.to_numeric(m1[0], errors="coerce")
        high = pd.to_numeric(m1[1], errors="coerce")
        low2 = low.where(low <= high, high)
        high2 = high.where(high >= low, low)
        out.loc[has_m1] = low2.loc[has_m1].round(1).astype("string") + "-" + high2.loc[has_m1].round(1).astype("string") + "K/月"
        out = out.str.replace(".0K/月", "K/月", regex=False)

    m2 = t.str.extract(RE_SALARY_K_PLUS, expand=True)
    has_m2 = m2[0].notna() & (out == "")
    if has_m2.any():
        v = pd.to_numeric(m2[0], errors="coerce").round(1).astype("string")
        out.loc[has_m2] = v.loc[has_m2] + "K+/月"
        out = out.str.replace(".0K+/月", "K+/月", regex=False)

    m3 = t.str.extract(RE_SALARY_DAY_RANGE, expand=True)
    has_m3 = m3[0].notna() & m3[1].notna() & (out == "")
    if has_m3.any():
        low = pd.to_numeric(m3[0], errors="coerce") * 21.75 / 1000
        high = pd.to_numeric(m3[1], errors="coerce") * 21.75 / 1000
        low2 = low.where(low <= high, high)
        high2 = high.where(high >= low, low)
        out.loc[has_m3] = low2.loc[has_m3].round(1).astype("string") + "-" + high2.loc[has_m3].round(1).astype("string") + "K/月"
    return out.fillna("")


def vectorized_normalize_degree(text_s: pd.Series) -> pd.Series:
    # 性能优化：学历标准化向量化，替代逐行 map(normalize_degree)
    t = text_s.fillna("").astype("string")
    out = pd.Series("其他", index=t.index, dtype="string")
    out = out.where(~t.str.contains(r"(不限学历|学历不限)", regex=True, na=False), "不限")
    out = out.where(~t.str.contains(r"(大专及以上|大专)", regex=True, na=False), "大专")
    out = out.where(~t.str.contains(r"(本科及以上|本科)", regex=True, na=False), "本科")
    out = out.where(~t.str.contains(r"(硕士及以上|硕士|研究生)", regex=True, na=False), "硕士")
    out = out.where(~t.str.contains(r"(博士)", regex=True, na=False), "博士")
    out = out.where(t.str.strip() != "", "")
    return out


def vectorized_normalize_years_experience(text_s: pd.Series) -> pd.Series:
    # 性能优化：年限提取向量化，替代逐行 map(normalize_years_experience)
    t = text_s.fillna("").astype("string")
    out = pd.Series("", index=t.index, dtype="string")
    m1 = t.str.extract(RE_EXP_RANGE, expand=True)
    has_m1 = m1[0].notna() & m1[1].notna()
    if has_m1.any():
        low = pd.to_numeric(m1[0], errors="coerce").fillna(0).astype(int)
        high = pd.to_numeric(m1[1], errors="coerce").fillna(0).astype(int)
        low2 = low.where(low <= high, high).astype("string")
        high2 = high.where(high >= low, low).astype("string")
        out.loc[has_m1] = low2.loc[has_m1] + "-" + high2.loc[has_m1] + "年"
    m2 = t.str.extract(RE_EXP_PLUS, expand=True)
    has_m2 = m2[0].notna() & (out == "")
    out.loc[has_m2] = pd.to_numeric(m2.loc[has_m2, 0], errors="coerce").fillna(0).astype(int).astype("string") + "年+"
    m3 = t.str.extract(RE_EXP_ANY, expand=True)
    has_m3 = m3[0].notna() & (out == "")
    out.loc[has_m3] = pd.to_numeric(m3.loc[has_m3, 0], errors="coerce").fillna(0).astype(int).astype("string") + "年"
    zero_mask = t.str.contains(RE_EXP_ZERO, regex=True, na=False) & (out == "")
    out.loc[zero_mask] = "0年"
    return out


def vectorized_trust_score(df: pd.DataFrame) -> pd.Series:
    # 性能优化：可信度计算向量化，替代 apply(trust_score_row, axis=1)
    src = df.get("publish_time_source", pd.Series("", index=df.index)).fillna("").astype("string")
    estimated = df.get("publish_time_estimated", pd.Series("", index=df.index)).fillna("").astype("string")
    cached = df.get("cache_fallback_tag", pd.Series("", index=df.index)).fillna("").astype("string")
    score = pd.Series(0.3, index=df.index, dtype="float64")
    score = score.where(~estimated.str.strip().ne(""), 0.6)
    score = score.where(~src.eq("official_update_proxy"), 0.8)
    score = score.where(~src.str.startswith("real"), 1.0)
    score = score.where(~cached.str.strip().ne(""), score.clip(upper=0.6))
    return score


def parse_publish_time(value):
    t = normalize_text(value)
    if not t or t in {"不知道发布时间", "unknown", "nan", "none"}:
        return pd.NaT
    t = t.replace("年", "-").replace("月", "-").replace("日", "")
    t = t.replace("/", "-").replace(".", "-")
    t = re.sub(r"\s+", " ", t)
    return pd.to_datetime(t, errors="coerce")


def is_publish_time_abnormal(value):
    ts = parse_publish_time(value)
    if pd.isna(ts):
        return True
    today = pd.Timestamp(datetime.now().date())
    if ts > today + pd.Timedelta(days=1):
        return True
    if ts < pd.Timestamp("2010-01-01"):
        return True
    return False


def trust_score_row(row):
    src = normalize_text(row.get("publish_time_source", ""))
    estimated = normalize_text(row.get("publish_time_estimated", ""))
    cached = normalize_text(row.get("cache_fallback_tag", ""))
    if src.startswith("real"):
        base = 1.0
    elif src == "official_update_proxy":
        base = 0.8
    elif estimated:
        base = 0.6
    else:
        base = 0.3
    if cached:
        base = min(base, 0.6)
    return base


def map_shixiseng(df):
    mapped = pd.DataFrame(
        {
            "url": df.get("url", ""),
            "company": df.get("company", ""),
            "name": df.get("name", ""),
            "city": df.get("city", ""),
            "jd_raw": df.get("info", ""),
            "salary": df.get("salary", ""),
            "company_size": df.get("company_size", ""),
            "duration": df.get("duration", ""),
            "academic": df.get("academic", ""),
            "publish_time": "",
            "deadline": "",
            "collect_time": "",
            "source": "shixiseng",
            "publish_time_source": "unknown",
            "deadline_source": "unknown",
        }
    )
    return mapped


def map_bytedance(df):
    duties = df.get("岗位职责")
    if duties is None:
        duties = pd.Series([""] * len(df))
    reqs = df.get("岗位要求")
    if reqs is None:
        reqs = pd.Series([""] * len(df))
    pub = df.get("岗位发布时间", "")
    ddl = df.get("报名截止时间", "")
    ctime = df.get("采集时间", "")

    mapped = pd.DataFrame(
        {
            "url": df.get("投递链接", ""),
            "company": df.get("公司名", ""),
            "name": df.get("岗位名", ""),
            "city": df.get("工作城市", ""),
            "jd_raw": duties.fillna("").astype(str) + " 岗位要求：" + reqs.fillna("").astype(str),
            "salary": "",
            "company_size": "",
            "duration": "",
            "academic": "",
            "publish_time": pub,
            "publish_time_estimated": pub,
            "publish_time_estimated_source": "real_import",
            "deadline": ddl,
            "collect_time": ctime,
            "source": "bytedance",
            "publish_time_source": "real_import",
            "deadline_source": "real_import",
        }
    )
    return mapped


def map_official(df):
    mapped = pd.DataFrame(
        {
            "url": df.get("url", ""),
            "company": df.get("company", ""),
            "name": df.get("name", ""),
            "city": df.get("city", ""),
            "jd_raw": df.get("jd_raw", ""),
            "salary": df.get("salary", ""),
            "company_size": df.get("company_size", ""),
            "duration": df.get("duration", ""),
            "academic": df.get("academic", ""),
            "publish_time": df.get("publish_time", ""),
            "publish_time_estimated": df.get("publish_time_estimated", ""),
            "publish_time_estimated_source": df.get("publish_time_estimated_source", ""),
            "deadline": df.get("deadline", ""),
            "collect_time": df.get("collect_time", ""),
            "source": df.get("source", "official"),
            "publish_time_source": df.get("publish_time_source", ""),
            "deadline_source": df.get("deadline_source", ""),
            "recruit_type": df.get("recruit_type", ""),
            "raw_tags": df.get("raw_tags", ""),
            "external_job_id": df.get("external_job_id", ""),
            "update_time": df.get("update_time", ""),
            "sync_status": df.get("sync_status", ""),
            "cache_fallback_tag": df.get("cache_fallback_tag", ""),
            "fetch_status": df.get("fetch_status", ""),
        }
    )
    return mapped


def is_big_company(company):
    c = normalize_text(company)
    return any(k.lower() in c.lower() for k in big_company_keywords)


def vectorized_is_big_company(company_s: pd.Series) -> pd.Series:
    # 性能优化：公司匹配向量化，替代逐行 map(is_big_company)
    c = company_s.fillna("").astype("string").str.lower()
    pattern = "|".join(re.escape(k.lower()) for k in big_company_keywords)
    return c.str.contains(pattern, regex=True, na=False)


def is_official_priority_company(company):
    c = normalize_text(company)
    return any(k in c for k in OFFICIAL_PRIORITY_COMPANY_KEYWORDS)


def is_27_match(text):
    t = normalize_text(text).lower()
    if any(k.lower() in t for k in grade_keywords):
        return True
    if re.search(r"(26|2026).{0,8}(27|2027)", t):
        return True
    if re.search(r"(27|2027).{0,8}(及以后|以后)", t):
        return True
    return False


def vectorized_is_27_match(text_s: pd.Series) -> pd.Series:
    # 性能优化：27届识别向量化，替代逐行 map(is_27_match)
    t = text_s.fillna("").astype("string").str.lower()
    base_pat = "|".join(re.escape(k.lower()) for k in grade_keywords)
    m1 = t.str.contains(base_pat, regex=True, na=False)
    m2 = t.str.contains(RE_27_PAIR, regex=True, na=False)
    m3 = t.str.contains(RE_27_AFTER, regex=True, na=False)
    return m1 | m2 | m3


def role_match_score(text):
    t = normalize_text(text).lower()
    hit = sum(1 for k in role_keywords if k.lower() in t)
    return min(hit * 5, 30)


def vectorized_role_match_score(text_s: pd.Series) -> pd.Series:
    # 性能优化：岗位关键词计分向量化，替代逐行 role_match_score
    t = text_s.fillna("").astype("string").str.lower()
    hits = pd.Series(0, index=t.index, dtype="int16")
    for k in role_keywords:
        hits = hits + t.str.contains(re.escape(k.lower()), regex=True, na=False).astype("int16")
    return (hits * 5).clip(upper=30)


def jd_quality_score(resp, req):
    fields = [normalize_text(resp), normalize_text(req)]
    non_empty = sum(1 for x in fields if x)
    length_score = min((len(fields[0]) + len(fields[1])) // 120, 10)
    return non_empty * 5 + length_score


def vectorized_jd_quality_score(resp_s: pd.Series, req_s: pd.Series) -> pd.Series:
    # 性能优化：JD质量分向量化，替代逐行 jd_quality_score
    resp = resp_s.fillna("").astype("string")
    req = req_s.fillna("").astype("string")
    non_empty = (resp.str.len() > 0).astype("int16") + (req.str.len() > 0).astype("int16")
    length_score = ((resp.str.len() + req.str.len()) // 120).clip(upper=10).astype("int16")
    return non_empty * 5 + length_score


def score_row(row):
    score = 0
    company = normalize_text(row.get("company", ""))
    city = normalize_text(row.get("city", ""))
    jd = normalize_text(row.get("jd_raw", ""))
    resp = normalize_text(row.get("responsibility", ""))
    req = normalize_text(row.get("requirement", ""))
    name = normalize_text(row.get("name", ""))
    text = f"{name} {jd} {req}"

    if is_big_company(company):
        score += 20
    if TARGET_CITY in city:
        score += 20
    if is_27_match(text):
        score += 20
    score += role_match_score(text)
    score += jd_quality_score(resp, req)
    if bool(row.get("is_dirty_data", False)):
        score -= 10
    return min(score, 100)


def extract_city_from_text(text):
    t = normalize_text(text)
    city_list = ["上海", "北京", "深圳", "广州", "杭州", "成都", "南京", "苏州", "武汉", "西安", "天津", "重庆", "青岛", "厦门", "大连"]
    for c in city_list:
        if c in t:
            return c
    return ""


def city_match_level(row):
    city = normalize_text(row.get("city", ""))
    location_text = normalize_text(f"{row.get('city', '')} {row.get('jd_raw', '')}")
    if TARGET_CITY in city:
        return "strict_shanghai"
    if any(k in city for k in SHANGHAI_VARIANTS):
        return "contains_shanghai"
    if any(k in location_text for k in SHANGHAI_VARIANTS):
        if any(x in location_text for x in ["/", "、", "全国", "多地", "异地"]):
            return "multi_base_contains_shanghai"
        return "contains_shanghai"
    return "unknown"


def enrich_cohort27_fields(row):
    signal = {
        "title": row.get("name", ""),
        "jd_raw": row.get("jd_raw", ""),
        "source": row.get("source", ""),
        "recruit_type": row.get("recruit_type", ""),
        "collect_time": row.get("collect_time", ""),
        "project_name": row.get("raw_tags", ""),
        "year_text": row.get("graduation_batch", ""),
    }
    return classify_27_cohort(signal)


def infer_27_from_context(row):
    text = normalize_text(f"{row.get('name', '')} {row.get('jd_raw', '')} {row.get('source', '')} {row.get('recruit_type', '')} {row.get('raw_tags', '')}").lower()
    if is_27_match(text):
        return True
    src = normalize_text(row.get("source", ""))
    if src in {"official_tencent_api", "official_jd_api", "official_baidu_api", "official_bilibili", "official_kuaishou_api", "official_meituan", "official_alibaba"}:
        return True
    if any(k in text for k in ["校园", "校招", "应届", "留用实习", "实习生", "暑期实习", "转正", "留用", "提前锁定", "x-star", "xstar", "快star", "kstar", "redstar", "red star", "青锐计划", "北斗计划", "技术大咖", "跃动计划", "产培生", "大咖实习", "青云计划", "新星计划", "bilibili星", "珠峰计划", "新锐之星", "天才计划"]):
        return True
    return False


def vectorized_infer_27(frame: pd.DataFrame) -> pd.Series:
    # 性能优化：27届上下文推断向量化，替代 apply(infer_27_from_context, axis=1)
    text = (
        frame["name"].fillna("").astype("string")
        + " " + frame["jd_raw"].fillna("").astype("string")
        + " " + frame["source"].fillna("").astype("string")
        + " " + frame["recruit_type"].fillna("").astype("string")
        + " " + frame["raw_tags"].fillna("").astype("string")
    ).str.lower()
    m27 = vectorized_is_27_match(text)
    src = frame["source"].fillna("").astype("string")
    src_hit = src.isin(
        {
            "official_tencent_api",
            "official_jd_api",
            "official_baidu_api",
            "official_bilibili",
            "official_kuaishou_api",
            "official_meituan",
            "official_alibaba",
        }
    )
    ctx_hit = text.str.contains(r"校园|校招|应届|留用实习|实习生|暑期实习|转正|留用|提前锁定|x-star|xstar|快star|kstar|redstar|red star|青锐计划|北斗计划|技术大咖|跃动计划|产培生|大咖实习|青云计划|新星计划|bilibili星|珠峰计划|新锐之星|天才计划", regex=True, na=False)
    return m27 | src_hit | ctx_hit


def vectorized_score(frame: pd.DataFrame) -> pd.Series:
    # 性能优化：评分拆解为列级向量化，替代 apply(score_row, axis=1)
    text = (
        frame["name"].fillna("").astype("string")
        + " " + frame["jd_raw"].fillna("").astype("string")
        + " " + frame["requirement"].fillna("").astype("string")
    )
    company_score = frame["is_big_company"].astype("int16") * 20
    city_score = frame["city"].fillna("").astype("string").str.contains(TARGET_CITY, regex=False, na=False).astype("int16") * 20
    match27_score = vectorized_is_27_match(text).astype("int16") * 20
    role_score = vectorized_role_match_score(text)
    jd_score = vectorized_jd_quality_score(frame["responsibility"], frame["requirement"])
    dirty_penalty = frame.get("is_dirty_data", pd.Series(False, index=frame.index)).astype(bool).astype("int16") * 10
    return (company_score + city_score + match27_score + role_score + jd_score - dirty_penalty).clip(upper=100)


def build_quality_report(df):
    rows = []
    key_cols = ["company", "name", "city", "url", "jd_raw", "requirement"]
    unknown_marker = "不知道发布时间"
    for src, g in df.groupby("source"):
        item = {"source": src, "rows": len(g)}
        for col in key_cols:
            item[f"{col}_完整率"] = round((g[col].astype(str).str.strip() != "").mean() * 100, 2)
        p = g["publish_time"].fillna("").astype(str).str.strip()
        pe = g.get("publish_time_estimated", pd.Series([""] * len(g))).fillna("").astype(str).str.strip()
        ps = g.get("publish_time_source", pd.Series([""] * len(g))).fillna("").astype(str).str.strip()
        item["publish_time_可用率"] = round(((p != "") & (p != unknown_marker)).mean() * 100, 2)
        item["publish_time_估算可用率"] = round((pe != "").mean() * 100, 2)
        item["publish_time_真实率"] = round(ps.str.startswith("real").mean() * 100, 2)
        item["publish_time_代理率"] = round((ps == "official_update_proxy").mean() * 100, 2)
        dirty = g.get("is_dirty_data", pd.Series([False] * len(g), index=g.index)).astype(bool)
        dirty_jd = g.get("dirty_jd_short", pd.Series([False] * len(g), index=g.index)).astype(bool)
        dirty_url = g.get("dirty_url_unreachable", pd.Series([False] * len(g), index=g.index)).astype(bool)
        dirty_pub = g.get("dirty_publish_time_abnormal", pd.Series([False] * len(g), index=g.index)).astype(bool)
        salary_norm = g.get("salary_normalized", pd.Series([""] * len(g), index=g.index)).fillna("").astype(str).str.strip()
        degree_norm = g.get("degree_normalized", pd.Series([""] * len(g), index=g.index)).fillna("").astype(str).str.strip()
        years_norm = g.get("years_experience_normalized", pd.Series([""] * len(g), index=g.index)).fillna("").astype(str).str.strip()
        trust = vectorized_trust_score(g)
        cache_ratio = g.get("cache_fallback_tag", pd.Series([""] * len(g), index=g.index)).fillna("").astype(str).str.strip()
        item["脏数据占比"] = round(dirty.mean() * 100, 2)
        item["JD短文本占比"] = round(dirty_jd.mean() * 100, 2)
        item["URL异常占比"] = round(dirty_url.mean() * 100, 2)
        item["发布时间异常占比"] = round(dirty_pub.mean() * 100, 2)
        item["薪资标准化覆盖率"] = round((salary_norm != "").mean() * 100, 2)
        item["学历标准化覆盖率"] = round((degree_norm != "").mean() * 100, 2)
        item["年限标准化覆盖率"] = round((years_norm != "").mean() * 100, 2)
        item["可信度均值"] = round(trust.mean() * 100, 2)
        item["缓存补位占比"] = round((cache_ratio != "").mean() * 100, 2)
        rows.append(item)
    overall = {"source": "all", "rows": len(df)}
    for col in key_cols:
        overall[f"{col}_完整率"] = round((df[col].astype(str).str.strip() != "").mean() * 100, 2)
    p = df["publish_time"].fillna("").astype(str).str.strip()
    pe = df.get("publish_time_estimated", pd.Series([""] * len(df))).fillna("").astype(str).str.strip()
    ps = df.get("publish_time_source", pd.Series([""] * len(df))).fillna("").astype(str).str.strip()
    overall["publish_time_可用率"] = round(((p != "") & (p != unknown_marker)).mean() * 100, 2)
    overall["publish_time_估算可用率"] = round((pe != "").mean() * 100, 2)
    overall["publish_time_真实率"] = round(ps.str.startswith("real").mean() * 100, 2)
    overall["publish_time_代理率"] = round((ps == "official_update_proxy").mean() * 100, 2)
    dirty = df.get("is_dirty_data", pd.Series([False] * len(df), index=df.index)).astype(bool)
    dirty_jd = df.get("dirty_jd_short", pd.Series([False] * len(df), index=df.index)).astype(bool)
    dirty_url = df.get("dirty_url_unreachable", pd.Series([False] * len(df), index=df.index)).astype(bool)
    dirty_pub = df.get("dirty_publish_time_abnormal", pd.Series([False] * len(df), index=df.index)).astype(bool)
    salary_norm = df.get("salary_normalized", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    degree_norm = df.get("degree_normalized", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    years_norm = df.get("years_experience_normalized", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    trust = vectorized_trust_score(df)
    cache_ratio = df.get("cache_fallback_tag", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    overall["脏数据占比"] = round(dirty.mean() * 100, 2)
    overall["JD短文本占比"] = round(dirty_jd.mean() * 100, 2)
    overall["URL异常占比"] = round(dirty_url.mean() * 100, 2)
    overall["发布时间异常占比"] = round(dirty_pub.mean() * 100, 2)
    overall["薪资标准化覆盖率"] = round((salary_norm != "").mean() * 100, 2)
    overall["学历标准化覆盖率"] = round((degree_norm != "").mean() * 100, 2)
    overall["年限标准化覆盖率"] = round((years_norm != "").mean() * 100, 2)
    overall["可信度均值"] = round(trust.mean() * 100, 2)
    overall["缓存补位占比"] = round((cache_ratio != "").mean() * 100, 2)
    official_scope = df[df["source"].astype(str).str.contains("official|bytedance", case=False, regex=True)]
    if not official_scope.empty:
        osp = official_scope.get("publish_time_source", pd.Series([""] * len(official_scope))).fillna("").astype(str).str.strip()
        ope = official_scope.get("publish_time_estimated", pd.Series([""] * len(official_scope))).fillna("").astype(str).str.strip()
        overall["大厂发布时间真实覆盖率"] = round(osp.str.startswith("real").mean() * 100, 2)
        overall["大厂发布时间有效覆盖率"] = round((osp.str.startswith("real") | (osp == "official_update_proxy")).mean() * 100, 2)
        overall["大厂发布时间估算可用率"] = round((ope != "").mean() * 100, 2)
    rows.append(overall)
    return pd.DataFrame(rows)


def build_skill_gap_report(target_df):
    text_series = (target_df["name"].fillna("") + " " + target_df["jd_raw"].fillna("") + " " + target_df["requirement"].fillna("")).str.lower()
    counter = Counter()
    for text in text_series.tolist():
        for k in skill_keywords:
            if k.lower() in text:
                counter[k] += 1
    report = pd.DataFrame({"skill": list(counter.keys()), "count": list(counter.values())}).sort_values("count", ascending=False)
    if report.empty:
        report = pd.DataFrame({"skill": skill_keywords, "count": [0] * len(skill_keywords)})
    report["coverage_pct"] = (report["count"] / max(len(target_df), 1) * 100).round(2)
    return report


def classify_role_type(row):
    text = normalize_text(f"{row.get('name', '')} {row.get('jd_raw', '')}").lower()
    if re.search(r"(数据分析|商业分析|策略分析|经营分析|bi|tableau|power bi)", text):
        return "数据分析"
    if re.search(r"(数据开发|数据工程|数仓|数据仓库|hadoop|spark|hive|etl)", text):
        return "数据开发"
    if re.search(r"(算法|机器学习|推荐|搜索|nlp|cv|深度学习)", text):
        return "算法"
    return "其他"


def is_data_job(row):
    text = normalize_text(f"{row.get('name', '')} {row.get('jd_raw', '')}").lower()
    return bool(re.search(r"(数据|分析|策略|算法|商业分析|bi|python|sql)", text))


def count_priority_skill_hits(row):
    text = normalize_text(f"{row.get('name', '')} {row.get('jd_raw', '')} {row.get('requirement', '')}").lower()
    return sum(1 for k in priority_skill_keywords if k.lower() in text)


def _load_csv_if_exists(path):
    if os.path.exists(path):
        try:
            return pd.read_csv(path, dtype="string", keep_default_na=False)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


# 性能优化：读取CSV时指定dtype，降低类型推断和内存开销
READ_DTYPE = {
    "url": "string",
    "company": "string",
    "name": "string",
    "city": "string",
    "info": "string",
    "salary": "string",
    "company_size": "string",
    "duration": "string",
    "academic": "string",
    "source": "string",
    "jd_raw": "string",
    "publish_time": "string",
    "deadline": "string",
    "collect_time": "string",
    "recruit_type": "string",
    "raw_tags": "string",
    "external_job_id": "string",
    "update_time": "string",
}


def read_csv_fast(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype=READ_DTYPE, keep_default_na=False)


def compute_priority_score(row):
    if normalize_text(row.get("cohort27_confidence", "")) != "high":
        return 0
    text = normalize_text(f"{row.get('name', '')} {row.get('jd_raw', '')} {row.get('requirement', '')}").lower()
    score = 0
    if "python" in text and "sql" in text:
        score += 20
    if "spark" in text or "hadoop" in text:
        score += 15
    if TARGET_CITY in normalize_text(row.get("city", "")):
        score += 10
    if normalize_text(row.get("company", "")) in {"快手", "腾讯"}:
        score += 10
    return score


def attach_link_health(frame, companies=None, max_concurrent=12, timeout=6):
    if companies is None:
        companies = ["快手", "腾讯"]
    check_df = frame[frame["company"].isin(companies)][["company", "name", "url"]].copy()
    check_df["url"] = normalize_text_series(check_df["url"])
    check_df = check_df[check_df["url"] != ""]
    check_df = check_df.drop_duplicates(subset=["url"], keep="first")
    if check_df.empty:
        frame["link_status"] = frame.get("link_status", "UNKNOWN")
        frame["link_reason"] = frame.get("link_reason", "")
        return frame, pd.DataFrame(columns=["company", "url", "status", "reason"])
    urls = check_df["url"].tolist()
    results = asyncio.run(check_links_batch(urls, max_concurrent=max_concurrent, timeout=timeout))
    result_df = pd.DataFrame(results)
    if result_df.empty:
        frame["link_status"] = frame.get("link_status", "UNKNOWN")
        frame["link_reason"] = frame.get("link_reason", "")
        return frame, pd.DataFrame(columns=["company", "url", "status", "reason"])
    link_health_file = health_path("link_health_latest.csv")
    broken_report_file = health_path("broken_links_report.csv")
    if os.path.exists(link_health_file):
        prev = _load_csv_if_exists(link_health_file)
        if not prev.empty and {"url", "status"}.issubset(set(prev.columns)):
            prev = prev[["url", "status"]].rename(columns={"status": "prev_status"})
            result_df = result_df.merge(prev, on="url", how="left")
            result_df.loc[(result_df["status"] == "RISKY") & (result_df["prev_status"] == "RISKY"), "status"] = "BROKEN"
            result_df.loc[(result_df["reason"] == "") & (result_df["status"] == "BROKEN"), "reason"] = "RISKY two days"
    result_df.to_csv(link_health_file, index=False, encoding="utf-8-sig")
    report_df = check_df.merge(result_df, on="url", how="left")
    report_df["status"] = report_df["status"].fillna("UNKNOWN")
    report_df["reason"] = report_df["reason"].fillna("")
    report_df = report_df.sort_values(["status", "company", "name"], ascending=[True, True, True])
    report_df.to_csv(broken_report_file, index=False, encoding="utf-8-sig")
    link_map = result_df[["url", "status", "reason"]].rename(columns={"status": "link_status", "reason": "link_reason"})
    frame = frame.merge(link_map, on="url", how="left")
    frame["link_status"] = frame["link_status"].fillna("UNKNOWN")
    frame["link_reason"] = frame["link_reason"].fillna("")
    return frame, report_df


def generate_company_dashboard(df_all, company_name):
    df_ks = df_all[df_all["company"] == company_name].copy()
    if df_ks.empty:
        print(f"[Dashboard] {company_name}看板跳过：当前无数据")
        return {}

    company_slug_map = {
        "快手": "kuaishou",
        "腾讯": "tencent",
        "字节跳动": "bytedance",
        "小红书": "xiaohongshu",
        "美团": "meituan",
        "阿里": "alibaba",
        "京东": "jd",
        "哔哩哔哩": "bilibili",
        "百度": "baidu",
    }
    slug = company_slug_map.get(company_name, normalize_text(company_name).lower())
    today = datetime.now().strftime("%Y-%m-%d")
    dashboard_latest_path = dashboard_path(f"dashboard_{slug}_latest.csv")
    summary_path = dashboard_path(f"dashboard_{slug}_summary.csv")
    role_path = dashboard_path(f"dashboard_{slug}_role_distribution.csv")
    keyword_path = dashboard_path(f"dashboard_{slug}_keyword_top10.csv")
    new_high_path = dashboard_path(f"dashboard_{slug}_new_high_sh_data.csv")
    close_warn_path = dashboard_path(f"dashboard_{slug}_close_warning.csv")
    daily_trend_path = dashboard_path(f"dashboard_{slug}_daily_trend.csv")
    history_path = dashboard_path(f"dashboard_{slug}_history.csv")
    strict_snap_prev = dashboard_path(f"dashboard_{slug}_strict27_snapshot_prev.csv")
    strict_snap_latest = dashboard_path(f"dashboard_{slug}_strict27_snapshot_latest.csv")
    core_snap_prev = dashboard_path(f"dashboard_{slug}_core_snapshot_prev.csv")
    core_snap_latest = dashboard_path(f"dashboard_{slug}_core_snapshot_latest.csv")

    df_ks["collect_date"] = pd.to_datetime(df_ks["collect_time"], errors="coerce").dt.strftime("%Y-%m-%d")
    role_text = (df_ks["name"].fillna("") + " " + df_ks["jd_raw"].fillna("")).astype("string").str.lower()
    df_ks["role_type"] = "其他"
    df_ks.loc[role_text.str.contains(RE_ROLE_ANALYSIS, regex=True, na=False), "role_type"] = "数据分析"
    df_ks.loc[role_text.str.contains(RE_ROLE_ENGINEERING, regex=True, na=False), "role_type"] = "数据开发"
    df_ks.loc[role_text.str.contains(RE_ROLE_ALGO, regex=True, na=False), "role_type"] = "算法"
    df_ks["is_data_job"] = role_text.str.contains(RE_DATA_JOB, regex=True, na=False)
    df_ks["is_shanghai_city"] = df_ks["city"].astype(str).str.contains(TARGET_CITY, na=False)
    score_text = (df_ks["name"].fillna("") + " " + df_ks["jd_raw"].fillna("") + " " + df_ks["requirement"].fillna("")).astype("string").str.lower()
    df_ks["priority_skill_hit_count"] = 0
    for k in priority_skill_keywords:
        df_ks["priority_skill_hit_count"] += score_text.str.contains(re.escape(k.lower()), regex=True, na=False).astype("int16")
    df_ks["priority_label"] = ""
    df_ks.loc[
        (df_ks["cohort27_confidence"] == "high")
        & (df_ks["is_shanghai_city"])
        & (df_ks["is_data_job"])
        & (df_ks["priority_skill_hit_count"] >= 3),
        "priority_label",
    ] = "PRIORITY_A"
    df_ks["priority_score"] = 0
    cond_high = df_ks["cohort27_confidence"].eq("high")
    cond_py_sql = score_text.str.contains("python", na=False) & score_text.str.contains("sql", na=False)
    cond_spark = score_text.str.contains("spark|hadoop", regex=True, na=False)
    cond_city = df_ks["city"].astype("string").str.contains(TARGET_CITY, regex=False, na=False)
    cond_company = df_ks["company"].isin(["快手", "腾讯"])
    df_ks.loc[cond_high & cond_py_sql, "priority_score"] += 20
    df_ks.loc[cond_high & cond_spark, "priority_score"] += 15
    df_ks.loc[cond_high & cond_city, "priority_score"] += 10
    df_ks.loc[cond_high & cond_company, "priority_score"] += 10
    df_ks["is_core_target"] = (df_ks["cohort27_confidence"] == "high") & df_ks["is_shanghai_city"] & df_ks["is_data_job"]

    strict_now = df_ks[df_ks["cohort27_confidence"] == "high"].copy()
    strict_now_ids = set(strict_now["external_job_id"].astype(str).tolist()) if "external_job_id" in strict_now.columns else set()
    strict_prev_df = _load_csv_if_exists(strict_snap_latest)
    strict_prev_ids = set(strict_prev_df.get("external_job_id", pd.Series(dtype=str)).astype(str).tolist())
    strict_net_increase = len(strict_now_ids - strict_prev_ids)
    if os.path.exists(strict_snap_latest):
        try:
            if os.path.exists(strict_snap_prev):
                os.remove(strict_snap_prev)
            os.replace(strict_snap_latest, strict_snap_prev)
        except Exception:
            pass
    strict_now[["external_job_id", "name", "city", "collect_time", "update_time", "cohort27_confidence"]].to_csv(
        strict_snap_latest, index=False, encoding="utf-8-sig"
    )

    core_now = df_ks[df_ks["is_core_target"]].copy()
    core_now_ids = set(core_now["external_job_id"].astype(str).tolist()) if "external_job_id" in core_now.columns else set()
    core_prev_df = _load_csv_if_exists(core_snap_latest)
    core_prev_ids = set(core_prev_df.get("external_job_id", pd.Series(dtype=str)).astype(str).tolist())
    new_core_ids = core_now_ids - core_prev_ids
    new_core_today = core_now[core_now["external_job_id"].astype(str).isin(new_core_ids)].copy()
    if os.path.exists(core_snap_latest):
        try:
            if os.path.exists(core_snap_prev):
                os.remove(core_snap_prev)
            os.replace(core_snap_latest, core_snap_prev)
        except Exception:
            pass
    core_now[["external_job_id", "name", "city", "collect_time", "update_time", "cohort27_confidence", "url"]].to_csv(
        core_snap_latest, index=False, encoding="utf-8-sig"
    )

    city_dist = df_ks["city"].value_counts(dropna=False)
    shanghai_ratio = round((df_ks["city"].astype(str).str.contains(TARGET_CITY, na=False).mean()) * 100, 2)
    role_dist = df_ks["role_type"].value_counts().reset_index()
    role_dist.columns = ["role_type", "count"]
    role_dist["pct"] = (role_dist["count"] / max(len(df_ks), 1) * 100).round(2)

    text_series = (df_ks["name"].fillna("") + " " + df_ks["jd_raw"].fillna("")).str.lower()
    keyword_rows = []
    for k in dashboard_skill_keywords:
        hit = int(text_series.str.contains(re.escape(k.lower()), na=False).sum())
        keyword_rows.append({"keyword": k, "count": hit, "hit_rate_pct": round(hit / max(len(df_ks), 1) * 100, 2)})
    keyword_df = pd.DataFrame(keyword_rows).sort_values(["count", "keyword"], ascending=[False, True]).head(10)

    today_high_df = new_core_today[
        [
            "external_job_id",
            "name",
            "city",
            "cohort27_confidence",
            "priority_label",
            "priority_score",
            "priority_skill_hit_count",
            "recruit_type",
            "raw_tags",
            "link_status",
            "link_reason",
            "update_time",
            "url",
            "jd_raw",
        ]
    ].copy()
    today_high_df = today_high_df.sort_values(["update_time", "name"], ascending=[False, True])

    hist_today = core_now[["external_job_id", "name", "city", "update_time", "collect_time", "source"]].copy()
    hist_today["date"] = today
    hist_df = _load_csv_if_exists(history_path)
    hist_df = pd.concat([hist_df, hist_today], ignore_index=True)
    hist_df = hist_df.drop_duplicates(subset=["date", "external_job_id"], keep="last")
    hist_df.to_csv(history_path, index=False, encoding="utf-8-sig")

    recent = hist_df.copy()
    recent = recent[recent["date"] >= (datetime.now() - pd.Timedelta(days=3)).strftime("%Y-%m-%d")]
    warn_rows = []
    if not recent.empty:
        for job_id, g in recent.groupby("external_job_id"):
            g = g.sort_values("date")
            dates = g["date"].dropna().unique().tolist()
            if len(dates) >= 3:
                upd = g["update_time"].fillna("").astype(str).str.strip().unique().tolist()
                if len([x for x in upd if x]) <= 1:
                    row = g.iloc[-1].to_dict()
                    row["warning_reason"] = "连续3天在榜且更新时间未变化"
                    warn_rows.append(row)
    warn_df = pd.DataFrame(warn_rows)
    if not warn_df.empty:
        warn_df = warn_df.sort_values(["date", "name"], ascending=[False, True])

    daily_trend = hist_df.groupby("date", as_index=False).agg(核心岗位数=("external_job_id", "nunique"))
    daily_trend = daily_trend.sort_values("date")

    summary = pd.DataFrame(
        [
            {
                "date": today,
                "company": company_name,
                "total_jobs": len(df_ks),
                "confidence_high": int((df_ks["cohort27_confidence"] == "high").sum()),
                "confidence_medium": int((df_ks["cohort27_confidence"] == "medium").sum()),
                "confidence_low": int((df_ks["cohort27_confidence"] == "low").sum()),
                "confidence_none": int((df_ks["cohort27_confidence"] == "none").sum()),
                "strict27_net_increase_dod": int(strict_net_increase),
                "shanghai_ratio_pct": shanghai_ratio,
                "core_target_new_today": int(len(today_high_df)),
                "priority_a_new_today": int((today_high_df["priority_label"] == "PRIORITY_A").sum()),
                "broken_link_count": int((df_ks["link_status"] == "BROKEN").sum()),
                "risky_link_count": int((df_ks["link_status"] == "RISKY").sum()),
                "close_warning_count": int(len(warn_df)),
            }
        ]
    )

    df_ks.to_csv(dashboard_latest_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    role_dist.to_csv(role_path, index=False, encoding="utf-8-sig")
    keyword_df.to_csv(keyword_path, index=False, encoding="utf-8-sig")
    today_high_df.to_csv(new_high_path, index=False, encoding="utf-8-sig")
    warn_df.to_csv(close_warn_path, index=False, encoding="utf-8-sig")
    daily_trend.to_csv(daily_trend_path, index=False, encoding="utf-8-sig")
    print(f"[Dashboard] {company_name}看板已更新: {len(df_ks)} 条")

    return {
        "latest": dashboard_latest_path,
        "summary": summary_path,
        "role": role_path,
        "keyword": keyword_path,
        "new_high": new_high_path,
        "close_warn": close_warn_path,
        "daily_trend": daily_trend_path,
    }


def generate_all_summary_dashboard(frame):
    part = frame[frame["company"].isin(TARGET_COMPANIES)].copy()
    if part.empty:
        return ""
    summary = (
        part.groupby(["company", "source"], as_index=False)
        .agg(岗位数=("company", "count"))
        .sort_values(["岗位数", "company"], ascending=[False, True])
    )
    total = int(summary["岗位数"].sum())
    summary["占比_pct"] = (summary["岗位数"] / max(total, 1) * 100).round(2)
    out = dashboard_path("dashboard_all_summary.csv")
    summary.to_csv(out, index=False, encoding="utf-8-sig")
    return out


def safe_write_csv(df, file_name):
    full_path = report_path(file_name)
    try:
        df.to_csv(full_path, index=False, encoding="utf-8-sig")
        return full_path
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt = report_path(file_name.replace(".csv", f"_{ts}.csv"))
        df.to_csv(alt, index=False, encoding="utf-8-sig")
        return alt


def main():
    ensure_output_dirs()
    all_frames = []
    for filename in glob.glob(os.path.join(shixiseng_path, "*.csv")):
        try:
            df = read_csv_fast(filename)
            all_frames.append(map_shixiseng(df))
        except Exception as e:
            print(f"读取实习僧文件失败 {filename}: {e}")

    for filename in glob.glob(os.path.join(bytedance_output_path, "字节跳动校招岗位_*.csv")):
        try:
            df = read_csv_fast(filename)
            all_frames.append(map_bytedance(df))
        except Exception as e:
            print(f"读取字节文件失败 {filename}: {e}")

    if os.path.exists(official_raw_file):
        try:
            official_df = read_csv_fast(official_raw_file)
            all_frames.append(map_official(official_df))
        except Exception as e:
            print(f"读取官网文件失败 {official_raw_file}: {e}")

    if not all_frames:
        print("未找到可合并文件，请检查目录配置。")
        return

    frame = pd.concat(all_frames, axis=0, ignore_index=True, copy=False)
    normalize_cols = [
        "url", "company", "name", "city", "jd_raw", "salary", "company_size", "duration", "academic",
        "publish_time", "publish_time_estimated", "publish_time_estimated_source", "deadline", "collect_time", "source", "publish_time_source", "deadline_source", "recruit_type", "raw_tags",
        "external_job_id", "update_time", "sync_status", "cache_fallback_tag", "fetch_status"
    ]
    for col in normalize_cols:
        if col not in frame.columns:
            frame[col] = ""
    for col in normalize_cols:
        # 性能优化：核心文本列统一向量化归一并缓存复用
        frame[col] = normalize_text_series(frame[col])

    pattern_official_priority = "|".join(re.escape(k) for k in OFFICIAL_PRIORITY_COMPANY_KEYWORDS)
    frame = frame[~((frame["source"] == "shixiseng") & frame["company"].str.contains(pattern_official_priority, regex=True, na=False))]

    frame.loc[(frame["city"] == "") & frame["jd_raw"].str.contains(TARGET_CITY, na=False), "city"] = TARGET_CITY
    frame["city"] = frame["city"].where(frame["city"] != "", frame["jd_raw"].str.extract(r"(上海|北京|深圳|广州|杭州|成都|南京|苏州|武汉|西安|天津|重庆|青岛|厦门|大连)", expand=False).fillna(""))
    # 性能优化：normalize_city仍需双字段语义，保留必要逐行调用
    frame["city"] = pd.Series(
        [normalize_city(c, j) for c, j in zip(frame["city"].tolist(), frame["jd_raw"].tolist())],
        index=frame.index,
        dtype="string",
    )
    frame["name"] = frame["name"].str.replace(RE_NAME_CLEAN_COMPANY, "", regex=True)
    frame["name"] = frame["name"].str.replace(RE_NAME_CLEAN_LOCATION, "", regex=True)
    frame["name"] = frame["name"].str.replace(RE_NAME_CLEAN_MAP, "", regex=True)

    # 性能优化：JD职责/要求改为str.extract向量化
    jd_norm = frame["jd_raw"].fillna("").astype("string")
    resp = normalize_text_series(jd_norm.str.extract(RE_RESP, expand=True)[1].fillna(""))
    req = normalize_text_series(jd_norm.str.extract(RE_REQ, expand=True)[1].fillna(""))
    req = req.where(req != "", resp)
    req = req.where((resp != "") | (req != ""), jd_norm)
    frame["responsibility"] = resp
    frame["requirement"] = req
    frame["name"] = frame["name"].where(frame["name"] != "", frame["jd_raw"].str.extract(RE_CITY_FALLBACK, expand=False).fillna(""))
    frame["name"] = frame["name"].where(frame["name"] != "", "未提取岗位名")
    core_text = (frame["academic"] + " " + frame["jd_raw"]).astype("string")
    salary_text = frame["salary"].where(frame["salary"] != "", frame["jd_raw"])
    frame["degree"] = core_text.str.extract(RE_DEGREE, expand=False).fillna("")
    frame["salary_normalized"] = vectorized_normalize_salary(salary_text)
    frame["degree_normalized"] = vectorized_normalize_degree(frame["academic"] + " " + frame["degree"] + " " + frame["jd_raw"])
    frame["years_experience_normalized"] = vectorized_normalize_years_experience(frame["jd_raw"])
    frame["major_pref"] = ""
    # 性能优化：关键抽取改用str.extract向量化
    frame["intern_days"] = frame["jd_raw"].str.extract(RE_INTERN_DAYS, expand=False).fillna("")
    frame["intern_months"] = frame["jd_raw"].str.extract(RE_INTERN_MONTHS, expand=False).fillna("")
    frame["graduation_batch"] = frame["jd_raw"].str.extract(RE_GRAD_BATCH, expand=False).fillna("")
    # 性能优化：避免DataFrame.apply，改为字典列表推导调用规则引擎
    cohort_signals = [
        {
            "title": n,
            "jd_raw": j,
            "source": s,
            "recruit_type": r,
            "collect_time": c,
            "project_name": t,
            "year_text": y,
        }
        for n, j, s, r, c, t, y in zip(
            frame["name"].tolist(),
            frame["jd_raw"].tolist(),
            frame["source"].tolist(),
            frame["recruit_type"].tolist(),
            frame["collect_time"].tolist(),
            frame["raw_tags"].tolist(),
            frame["graduation_batch"].tolist(),
        )
    ]
    cohort_results = [classify_27_cohort(x) for x in cohort_signals]
    cohort_df = pd.DataFrame(cohort_results)
    frame = pd.concat([frame, cohort_df], axis=1)
    frame["triggered_rules"] = [
        "|".join(x) if isinstance(x, list) else normalize_text(x)
        for x in frame["triggered_rules"].tolist()
    ]
    # 性能优化：城市匹配级别向量化，减少逐行函数开销
    location_text = (frame["city"].fillna("") + " " + frame["jd_raw"].fillna("")).astype("string")
    city_strict = frame["city"].str.contains(TARGET_CITY, regex=False, na=False)
    city_contains = frame["city"].str.contains("|".join(map(re.escape, SHANGHAI_VARIANTS)), regex=True, na=False)
    loc_contains = location_text.str.contains("|".join(map(re.escape, SHANGHAI_VARIANTS)), regex=True, na=False)
    loc_multi = location_text.str.contains(RE_MULTI_DELIMS, regex=True, na=False)
    frame["city_match_level"] = "unknown"
    frame.loc[city_strict, "city_match_level"] = "strict_shanghai"
    frame.loc[~city_strict & city_contains, "city_match_level"] = "contains_shanghai"
    frame.loc[~city_strict & ~city_contains & loc_contains & ~loc_multi, "city_match_level"] = "contains_shanghai"
    frame.loc[~city_strict & ~city_contains & loc_contains & loc_multi, "city_match_level"] = "multi_base_contains_shanghai"
    frame["is_shanghai_strict"] = frame["city_match_level"].eq("strict_shanghai")
    frame["is_shanghai_relaxed"] = frame["city_match_level"].isin(["strict_shanghai", "contains_shanghai", "multi_base_contains_shanghai"])
    frame["is_shanghai"] = frame["is_shanghai_relaxed"]
    frame["is_big_company"] = vectorized_is_big_company(frame["company"])
    # 性能优化：合并27匹配核心文本，只计算一次主表达式
    core_27_text = (frame["jd_raw"] + " " + frame["name"] + " " + frame["raw_tags"] + " " + frame["recruit_type"]).astype("string")
    frame["is_27_match"] = (
        vectorized_is_27_match(core_27_text)
        | frame["cohort27_confidence"].isin(["high", "medium"])
    )
    frame["is_27_inferred"] = vectorized_infer_27(frame) | frame["cohort27_confidence"].isin(["high", "medium"])

    frame = frame.drop_duplicates(subset=["company", "name", "city", "url"], keep="first")
    frame, link_report = attach_link_health(frame, companies=["快手", "腾讯", "字节跳动", "小红书", "美团", "阿里", "京东", "哔哩哔哩"], max_concurrent=12, timeout=6)
    frame["dirty_jd_short"] = frame["jd_raw"].str.len().fillna(0).astype("int32") < 50
    frame["dirty_url_unreachable"] = frame["link_status"].isin(["BROKEN", "RISKY"])
    publish_dt = pd.to_datetime(
        frame["publish_time"].fillna("").astype("string").str.replace(RE_TIME_YMD, "-", regex=True).str.replace("日", "", regex=False),
        errors="coerce",
    )
    today = pd.Timestamp(datetime.now().date())
    frame["dirty_publish_time_abnormal"] = publish_dt.isna() | (publish_dt > today + pd.Timedelta(days=1)) | (publish_dt < pd.Timestamp("2010-01-01"))
    # 性能优化：脏标签拼接向量化，替代逐行apply
    frame["dirty_tags"] = ""
    frame.loc[frame["dirty_jd_short"], "dirty_tags"] = "jd_short"
    frame.loc[frame["dirty_url_unreachable"], "dirty_tags"] = frame["dirty_tags"].where(frame["dirty_tags"] == "", frame["dirty_tags"] + "|") + "url_unreachable"
    frame.loc[frame["dirty_publish_time_abnormal"], "dirty_tags"] = frame["dirty_tags"].where(frame["dirty_tags"] == "", frame["dirty_tags"] + "|") + "publish_time_abnormal"
    frame["is_dirty_data"] = frame[["dirty_jd_short", "dirty_url_unreachable", "dirty_publish_time_abnormal"]].any(axis=1)
    # 性能优化：优先分向量化
    score_text = (frame["name"] + " " + frame["jd_raw"] + " " + frame["requirement"]).str.lower()
    frame["priority_score"] = 0
    cond_high = frame["cohort27_confidence"].eq("high")
    cond_py_sql = score_text.str.contains("python", na=False) & score_text.str.contains("sql", na=False)
    cond_spark = score_text.str.contains("spark|hadoop", regex=True, na=False)
    cond_city = frame["city"].str.contains(TARGET_CITY, regex=False, na=False)
    cond_company = frame["company"].isin(["快手", "腾讯"])
    frame.loc[cond_high & cond_py_sql, "priority_score"] += 20
    frame.loc[cond_high & cond_spark, "priority_score"] += 15
    frame.loc[cond_high & cond_city, "priority_score"] += 10
    frame.loc[cond_high & cond_company, "priority_score"] += 10

    out_master = safe_write_csv(frame, "internship_all_master.csv")
    out_legacy = safe_write_csv(frame, "internship_info_all.csv")

    quality = build_quality_report(frame)
    out_quality = safe_write_csv(quality, "data_quality_report.csv")

    target = frame
    target = target[target["is_shanghai_relaxed"] & target["is_big_company"] & target["is_27_inferred"]]
    target = target[~target["link_status"].isin(["BROKEN"])]
    target = target.copy(deep=False)
    target["score"] = vectorized_score(target)
    target = target.sort_values(by=["score", "company", "name"], ascending=[False, True, True])

    out_target = safe_write_csv(target, "internship_target_jobs.csv")
    strict_27 = frame[(frame["is_shanghai_relaxed"]) & (frame["is_big_company"]) & (frame["cohort27_confidence"] == "high")].copy()
    strict_27 = strict_27[~strict_27["link_status"].isin(["BROKEN"])]
    strict_27["score"] = vectorized_score(strict_27)
    strict_27 = strict_27.sort_values(by=["score", "company", "name"], ascending=[False, True, True])
    out_strict_27 = safe_write_csv(strict_27, "internship_target_strict_27.csv")
    out_a = safe_write_csv(target[target["score"] >= 80], "internship_target_A.csv")
    out_b = safe_write_csv(target[(target["score"] >= 65) & (target["score"] < 80)], "internship_target_B.csv")
    out_c = safe_write_csv(target[target["score"] < 65], "internship_target_C.csv")

    skill_gap = build_skill_gap_report(target)
    out_skill = safe_write_csv(skill_gap, "internship_skill_gap_report.csv")

    potential_27 = frame[(frame["is_shanghai_relaxed"]) & (frame["is_big_company"]) & (~frame["is_27_match"])].copy()
    potential_27["score"] = vectorized_score(potential_27)
    potential_27 = potential_27.sort_values(by=["score", "company", "name"], ascending=[False, True, True])
    out_potential = safe_write_csv(potential_27, "internship_target_potential_27.csv")

    inferred_27 = frame[(frame["is_shanghai_relaxed"]) & (frame["is_big_company"]) & (frame["is_27_inferred"])].copy()
    inferred_27 = inferred_27[~inferred_27["link_status"].isin(["BROKEN"])]
    inferred_27["score"] = vectorized_score(inferred_27)
    inferred_27 = inferred_27.sort_values(by=["score", "company", "name"], ascending=[False, True, True])
    out_inferred = safe_write_csv(inferred_27, "internship_target_inferred_27.csv")

    official_inferred = inferred_27[inferred_27["source"].str.startswith("official", na=False)].copy()
    out_official_inferred = safe_write_csv(official_inferred, "internship_target_official_inferred_27.csv")

    jd_delivery = inferred_27.copy()
    jd_delivery["jd_for_resume"] = jd_delivery["requirement"].where(jd_delivery["requirement"] != "", jd_delivery["jd_raw"])
    jd_delivery = jd_delivery[["company", "name", "city", "source", "score", "jd_for_resume", "url"]]
    jd_delivery = jd_delivery.sort_values(by=["score", "company"], ascending=[False, True])
    out_jd_delivery = safe_write_csv(jd_delivery, "internship_jd_resume_pack.csv")

    autumn_pack = pd.concat([target, official_inferred], axis=0, ignore_index=True)
    autumn_pack = autumn_pack.drop_duplicates(subset=["company", "name", "city", "url"], keep="first")
    autumn_pack = autumn_pack.sort_values(by=["score", "company", "name"], ascending=[False, True, True])
    out_autumn_pack = safe_write_csv(autumn_pack, "internship_autumn_27_bigtech_pack.csv")

    company_summary = (
        target.groupby("company", as_index=False)
        .agg(
            岗位数=("company", "count"),
            平均分=("score", "mean"),
        )
        .sort_values(by=["岗位数", "平均分"], ascending=[False, False])
    )
    company_summary["平均分"] = company_summary["平均分"].round(2)
    out_company_summary = safe_write_csv(company_summary, "internship_target_company_summary.csv")
    priority_top = strict_27[strict_27["priority_score"] > 0].copy()
    priority_top = priority_top.sort_values(["priority_score", "score"], ascending=[False, False]).head(20)
    out_priority_top = safe_write_csv(priority_top, "internship_priority_top20.csv")

    target_strict_shanghai = frame[(frame["is_shanghai_strict"]) & (frame["is_big_company"]) & (frame["is_27_inferred"]) & (~frame["link_status"].isin(["BROKEN"]))].copy()
    target_strict_shanghai["score"] = vectorized_score(target_strict_shanghai)
    target_strict_shanghai = target_strict_shanghai.sort_values(by=["score", "company", "name"], ascending=[False, True, True])
    out_target_strict_shanghai = safe_write_csv(target_strict_shanghai, "target_strict_shanghai.csv")
    out_target_relaxed_shanghai = safe_write_csv(target, "target_relaxed_shanghai.csv")

    city_audit = (
        frame.groupby(["company", "city_match_level"], as_index=False)
        .agg(rows=("company", "count"))
        .sort_values(["company", "rows"], ascending=[True, False])
    )
    out_city_audit = safe_write_csv(city_audit, "city_match_audit.csv")

    false_negative = frame[
        frame["cohort27_confidence"].isin(["none", "low"])
        & (
            frame["jd_raw"].str.contains(RE_FALSE_NEG, na=False)
            | frame["raw_tags"].str.contains(RE_FALSE_NEG, na=False)
            | frame["recruit_type"].str.contains(RE_FALSE_NEG, na=False)
        )
    ].copy()
    out_false_negative = safe_write_csv(false_negative, "cohort27_false_negative_audit.csv")

    sample_review = (
        false_negative.groupby("company", group_keys=False)
        .head(50)
        .sort_values(["company", "collect_time"], ascending=[True, False])
    )
    out_manual_sample = safe_write_csv(sample_review, "cohort27_manual_review_sample.csv")

    funnel = (
        frame[frame["is_big_company"]]
        .groupby("company", as_index=False)
        .agg(
            raw_count=("company", "count"),
            city_strict_count=("is_shanghai_strict", "sum"),
            city_relaxed_count=("is_shanghai_relaxed", "sum"),
            cohort_high=("cohort27_confidence", lambda s: int((s == "high").sum())),
            cohort_medium=("cohort27_confidence", lambda s: int((s == "medium").sum())),
            cohort_low=("cohort27_confidence", lambda s: int((s == "low").sum())),
            cohort_none=("cohort27_confidence", lambda s: int((s == "none").sum())),
            link_ok_count=("link_status", lambda s: int((~s.isin(["BROKEN"])).sum())),
        )
    )
    final_count = target.groupby("company", as_index=False).agg(final_target_count=("company", "count"))
    funnel = funnel.merge(final_count, on="company", how="left").fillna({"final_target_count": 0})
    funnel["final_target_count"] = funnel["final_target_count"].astype(int)
    out_funnel = safe_write_csv(funnel, "funnel_diagnostics_by_company.csv")

    delta = (
        funnel[["company", "city_strict_count", "city_relaxed_count", "final_target_count"]]
        .assign(
            strict_to_relaxed_delta=lambda d: d["city_relaxed_count"] - d["city_strict_count"],
            relaxed_to_final_gap=lambda d: d["city_relaxed_count"] - d["final_target_count"],
        )
        .sort_values(["strict_to_relaxed_delta", "company"], ascending=[False, True])
    )
    out_delta = safe_write_csv(delta, "funnel_before_after_delta.csv")
    out_pool_all_official = safe_write_csv(frame[frame["source"].str.contains("official|bytedance", case=False, regex=True)], "pool_all_official.csv")
    out_pool_city_relaxed = safe_write_csv(frame[frame["is_shanghai_relaxed"] & frame["is_big_company"]], "pool_city_relaxed.csv")
    out_pool_27_inferred = safe_write_csv(inferred_27, "pool_27_inferred.csv")
    out_pool_27_strict = safe_write_csv(strict_27, "pool_27_strict.csv")
    out_pool_delivery_priority = safe_write_csv(priority_top, "pool_delivery_priority.csv")

    dashboard_outputs_kuaishou = generate_company_dashboard(frame, "快手")
    dashboard_outputs_tencent = generate_company_dashboard(frame, "腾讯")
    dashboard_outputs_xiaohongshu = generate_company_dashboard(frame, "小红书")
    dashboard_outputs_meituan = generate_company_dashboard(frame, "美团")
    dashboard_outputs_alibaba = generate_company_dashboard(frame, "阿里")
    dashboard_outputs_jd = generate_company_dashboard(frame, "京东")
    dashboard_outputs_bilibili = generate_company_dashboard(frame, "哔哩哔哩")
    out_dashboard_all = generate_all_summary_dashboard(frame)

    print(f"主库岗位数: {len(frame)} -> {out_master}")
    print(f"兼容总表输出 -> {out_legacy}")
    print(f"目标岗位数: {len(target)} -> {out_target}")
    print(f"严格上海口径目标池 -> {out_target_strict_shanghai}")
    print(f"宽口径上海目标池 -> {out_target_relaxed_shanghai}")
    print(f"严格27届池（高置信）-> {out_strict_27}")
    print(f"质量报表 -> {out_quality}")
    print(f"A/B/C分层 -> {out_a} / {out_b} / {out_c}")
    print(f"能力差距报告 -> {out_skill}")
    print(f"潜在27届候选（大厂上海但未显式届别）-> {out_potential}")
    print(f"推断27届候选（用于扩充投递与JD准备）-> {out_inferred}")
    print(f"官网推断27届候选（优先用于简历准备）-> {out_official_inferred}")
    print(f"简历准备JD包 -> {out_jd_delivery}")
    print(f"秋招大厂综合包 -> {out_autumn_pack}")
    print(f"公司维度汇总 -> {out_company_summary}")
    print(f"优先投递Top20 -> {out_priority_top}")
    print(f"城市匹配审计 -> {out_city_audit}")
    print(f"27届误杀审计 -> {out_false_negative}")
    print(f"27届人工抽样 -> {out_manual_sample}")
    print(f"漏斗诊断 -> {out_funnel}")
    print(f"漏斗前后差异 -> {out_delta}")
    print(f"官方全量池 -> {out_pool_all_official}")
    print(f"上海宽口径池 -> {out_pool_city_relaxed}")
    print(f"27届推断池 -> {out_pool_27_inferred}")
    print(f"27届严格池 -> {out_pool_27_strict}")
    print(f"投递优先池 -> {out_pool_delivery_priority}")
    print(f"链接健康检查 -> {health_path('broken_links_report.csv')}")
    if dashboard_outputs_kuaishou:
        print(f"快手看板总表 -> {dashboard_outputs_kuaishou['latest']}")
        print(f"快手看板摘要 -> {dashboard_outputs_kuaishou['summary']}")
        print(f"快手新增高置信上海数据岗 -> {dashboard_outputs_kuaishou['new_high']}")
    if dashboard_outputs_tencent:
        print(f"腾讯看板总表 -> {dashboard_outputs_tencent['latest']}")
        print(f"腾讯看板摘要 -> {dashboard_outputs_tencent['summary']}")
        print(f"腾讯新增高置信上海数据岗 -> {dashboard_outputs_tencent['new_high']}")
    if dashboard_outputs_xiaohongshu:
        print(f"小红书看板总表 -> {dashboard_outputs_xiaohongshu['latest']}")
        print(f"小红书看板摘要 -> {dashboard_outputs_xiaohongshu['summary']}")
        print(f"小红书新增高置信上海数据岗 -> {dashboard_outputs_xiaohongshu['new_high']}")
    if dashboard_outputs_meituan:
        print(f"美团看板总表 -> {dashboard_outputs_meituan['latest']}")
        print(f"美团看板摘要 -> {dashboard_outputs_meituan['summary']}")
        print(f"美团新增高置信上海数据岗 -> {dashboard_outputs_meituan['new_high']}")
    if dashboard_outputs_alibaba:
        print(f"阿里看板总表 -> {dashboard_outputs_alibaba['latest']}")
        print(f"阿里看板摘要 -> {dashboard_outputs_alibaba['summary']}")
        print(f"阿里新增高置信上海数据岗 -> {dashboard_outputs_alibaba['new_high']}")
    if dashboard_outputs_jd:
        print(f"京东看板总表 -> {dashboard_outputs_jd['latest']}")
        print(f"京东看板摘要 -> {dashboard_outputs_jd['summary']}")
        print(f"京东新增高置信上海数据岗 -> {dashboard_outputs_jd['new_high']}")
    if dashboard_outputs_bilibili:
        print(f"B站看板总表 -> {dashboard_outputs_bilibili['latest']}")
        print(f"B站看板摘要 -> {dashboard_outputs_bilibili['summary']}")
        print(f"B站新增高置信上海数据岗 -> {dashboard_outputs_bilibili['new_high']}")
    if out_dashboard_all:
        print(f"多公司总览 -> {out_dashboard_all}")


if __name__ == "__main__":
    main()
