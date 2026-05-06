import glob
import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESUMINER = ROOT / "ResuMiner"
CDP_DIR = RESUMINER / "cdp_data"
OUT_DIR = ROOT / "release_data"


def norm(value):
    if value is None:
        return ""
    return str(value).strip()


def is_intern(*parts):
    text = " ".join(norm(x).lower() for x in parts)
    keys = ["实习", "intern", "byteintern", "暑期实习", "日常实习"]
    return any(key in text for key in keys)


def is_shanghai(city, *parts):
    text = " ".join([norm(city)] + [norm(x) for x in parts])
    return "上海" in text or "shanghai" in text.lower()


def append_row(rows, company, name, city, recruit_type, url, source, jd_raw, assume_intern=False):
    if not is_shanghai(city, name, recruit_type, jd_raw):
        return
    if (not assume_intern) and (not is_intern(name, recruit_type, jd_raw)):
        return
    rows.append(
        {
            "company": norm(company),
            "name": norm(name),
            "city": "上海",
            "recruit_type": norm(recruit_type),
            "url": norm(url),
            "source": norm(source),
            "jd_raw": norm(jd_raw),
        }
    )


def load_json_payload(file_name, key):
    path = CDP_DIR / file_name
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get(key, [])


def collect_bytedance(rows):
    files = sorted(
        glob.glob(str(ROOT / "real-useful-resume" / "output" / "字节跳动校招岗位_*.csv")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not files:
        return
    df = pd.read_csv(files[0])
    for _, r in df.iterrows():
        append_row(
            rows,
            "字节跳动",
            r.get("岗位名"),
            r.get("工作城市"),
            r.get("招聘类型"),
            r.get("投递链接"),
            "bytedance_crawler",
            f"{norm(r.get('岗位职责'))} {norm(r.get('岗位要求'))}",
        )


def collect_xiaohongshu(rows):
    path = RESUMINER / "outputs" / "raw" / "xiaohongshu_official_raw.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    for _, r in df.iterrows():
        append_row(
            rows,
            "小红书",
            r.get("name"),
            r.get("city"),
            r.get("recruit_type"),
            r.get("url"),
            "official_xiaohongshu_raw",
            r.get("jd_raw"),
        )


def collect_tencent(rows):
    for chunk in load_json_payload("tencent.json", "tencent"):
        for it in (chunk.get("data") or {}).get("positionList") or []:
            city = " ".join(
                norm(c.get("cityName")) for c in (it.get("workCities") or []) if isinstance(c, dict)
            )
            if not city:
                city = "上海"
            url = ""
            if it.get("postId"):
                url = f"https://join.qq.com/post.html?query=p_1&postId={norm(it.get('postId'))}"
            append_row(
                rows,
                "腾讯",
                it.get("positionTitle") or it.get("position"),
                city,
                it.get("projectName") or it.get("recruitLabelName"),
                url,
                "cdp_tencent",
                f"{norm(it.get('positionRequirement'))} {norm(it.get('positionResponsibility'))}",
                True,
            )


def collect_kuaishou(rows):
    for chunk in load_json_payload("kuaishou.json", "kuaishou"):
        for it in (chunk.get("result") or {}).get("list") or []:
            city = it.get("workLocationName") or it.get("workLocationCode") or it.get("cityName")
            if not norm(city):
                city = "上海"
            url = ""
            if it.get("id"):
                url = f"https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs/{norm(it.get('id'))}"
            append_row(
                rows,
                "快手",
                it.get("name"),
                city,
                it.get("positionNatureName") or it.get("positionNatureCode"),
                url,
                "cdp_kuaishou",
                f"{norm(it.get('description'))} {norm(it.get('positionDemand'))}",
                True,
            )


def collect_meituan(rows):
    for chunk in load_json_payload("meituan.json", "meituan"):
        for it in (chunk.get("data") or {}).get("list") or []:
            city = " ".join(
                norm(x.get("name") if isinstance(x, dict) else x) for x in (it.get("cityList") or [])
            )
            job_id = it.get("jobUnionId") or it.get("id")
            url = ""
            if job_id:
                url = f"https://zhaopin.meituan.com/web/campus/detail?jobUnionId={norm(job_id)}"
            append_row(
                rows,
                "美团",
                it.get("name"),
                city,
                it.get("projectName") or it.get("jobType"),
                url,
                "cdp_meituan",
                f"{norm(it.get('desc'))} {norm(it.get('jobDuty'))} {norm(it.get('jobRequirement'))}",
                True,
            )


def collect_alibaba(rows):
    for chunk in load_json_payload("alibaba.json", "alibaba"):
        for it in chunk.get("items") or []:
            append_row(
                rows,
                "阿里巴巴",
                it.get("title"),
                "上海",
                it.get("positionType"),
                it.get("url"),
                "cdp_alibaba",
                it.get("details"),
                True,
            )


def collect_jd(rows):
    for chunk in load_json_payload("jd.json", "jd"):
        for it in (chunk.get("body") or {}).get("items") or []:
            city = f"{norm(it.get('workCity'))} {norm(it.get('workAddress'))} {norm(it.get('city'))}"
            if not norm(city):
                city = "上海"
            req_id = it.get("publishId") or it.get("reqId")
            url = ""
            if req_id:
                url = f"https://campus.jd.com/#/jobs/{norm(req_id)}"
            append_row(
                rows,
                "京东",
                it.get("positionName"),
                city,
                it.get("positionTypeName") or it.get("positionType"),
                url,
                "cdp_jd",
                f"{norm(it.get('workContent'))} {norm(it.get('qualification'))}",
                True,
            )


def collect_bilibili(rows):
    for chunk in load_json_payload("bilibili.json", "bilibili"):
        for it in (chunk.get("data") or {}).get("list") or []:
            url = ""
            if it.get("id"):
                url = f"https://jobs.bilibili.com/campus/positions/{norm(it.get('id'))}"
            append_row(
                rows,
                "哔哩哔哩",
                it.get("positionName"),
                it.get("workLocation"),
                it.get("recruitType"),
                url,
                "cdp_bilibili",
                it.get("positionDescription"),
                True,
            )


def main():
    rows = []
    collect_bytedance(rows)
    collect_xiaohongshu(rows)
    collect_tencent(rows)
    collect_kuaishou(rows)
    collect_meituan(rows)
    collect_alibaba(rows)
    collect_jd(rows)
    collect_bilibili(rows)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.drop_duplicates(subset=["company", "name", "url"]).sort_values(["company", "name"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "internship_shanghai_latest.csv"
    out_xlsx = OUT_DIR / "internship_shanghai_latest.xlsx"
    old = None
    if out_csv.exists():
        try:
            old = pd.read_csv(out_csv)
        except Exception:
            old = None
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    out.to_excel(out_xlsx, index=False)

    new_count = len(out)
    if old is not None and len(old) > 0:
        old_key = set(
            (
                norm(x[0]),
                norm(x[1]),
                norm(x[2]),
            )
            for x in old[["company", "name", "url"]].fillna("").to_numpy()
        )
        out_key = out[["company", "name", "url"]].fillna("").to_numpy()
        is_new = [
            (norm(x[0]), norm(x[1]), norm(x[2])) not in old_key
            for x in out_key
        ]
        new_rows = out[is_new].copy()
        new_count = len(new_rows)
        new_csv = OUT_DIR / "internship_shanghai_new_this_update.csv"
        new_xlsx = OUT_DIR / "internship_shanghai_new_this_update.xlsx"
        new_rows.to_csv(new_csv, index=False, encoding="utf-8-sig")
        new_rows.to_excel(new_xlsx, index=False)
        print(f"saved {new_csv}")
        print(f"saved {new_xlsx}")

    print(f"saved {out_csv}")
    print(f"saved {out_xlsx}")
    print(f"total {len(out)}")
    print(f"new_this_update {new_count}")
    if not out.empty:
        print(out["company"].value_counts().to_string())


if __name__ == "__main__":
    main()
