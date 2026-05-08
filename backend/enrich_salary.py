"""B2: Backfill salary from JD text via DeepSeek."""
import os, sys, time, json, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from utils.no_proxy import *
from backend.db import get_db

API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

_PROMPT = """你是薪资信息提取助手。从下面的实习岗位 JD 中提取薪资范围。

岗位标题: {title}
JD: {jd}

只返回 JSON，格式：
{{"min": 200, "max": 300, "unit": "日"}}  // 元/日
{{"min": 6000, "max": 8000, "unit": "月"}}  // 元/月
{{"min": null, "max": null, "unit": "unknown"}}  // 未提及

unit 只能是: 日 / 月 / unknown
不要解释，只返回 JSON。"""


def _call(row: dict):
    if not DEEPSEEK_KEY:
        return {"min": None, "max": None, "unit": "unknown"}
    jd = (row.get("jd_raw", "") or "")[:1500]
    if len(jd) < 50:
        return {"min": None, "max": None, "unit": "unknown"}
    title = row.get("title", "")
    prompt = _PROMPT.format(title=title, jd=jd)
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 100},
            timeout=15,
        )
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return result
    except Exception as e:
        print(f"  API error: {e} | raw={raw if 'raw' in dir() else 'N/A'}")
        return {"min": None, "max": None, "unit": "unknown"}


def enrich_batch(limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, jd_raw FROM jobs WHERE (salary_unit IS NULL OR salary_unit='unknown') AND LENGTH(jd_raw) > 50 LIMIT ?",
        (limit,),
    ).fetchall()
    print(f"Rows to process: {len(rows)}")

    done = 0
    for r in rows:
        try:
            row_dict = dict(r)
        except Exception:
            row_dict = {"id": r[0], "title": r[1], "jd_raw": r[2]}
        result = _call(row_dict)
        if result["unit"] != "unknown":
            print(f"  #{row_dict['id']}: {result}")
        smin, smax, unit = result.get("min"), result.get("max"), result.get("unit")
        smin_kday = smax_kday = stored_unit = None
        if unit == "月" and smin and smax:
            smin_kday = round(smin / 22, 1)
            smax_kday = round(smax / 22, 1)
            stored_unit = "月"
        elif unit == "日":
            smin_kday, smax_kday, stored_unit = smin, smax, "日"
        else:
            stored_unit = "unknown"
        conn.execute(
            "UPDATE jobs SET salary_min_kday=?, salary_max_kday=?, salary_unit=? WHERE id=?",
            (smin_kday, smax_kday, stored_unit, row_dict["id"]),
        )
        done += 1
        if done % 5 == 0:
            conn.commit()
            print(f"  [{done}/{len(rows)}]")
    conn.commit()
    conn.close()
    print(f"Done: {done} rows enriched")


if __name__ == "__main__":
    enrich_batch(limit=10)
