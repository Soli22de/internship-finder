import json
import pandas as pd
import time
import sys
import os
from typing import List, Dict, Any

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from official_multi_crawler import (
    norm, normalize_time_value, is_time_like, UNKNOWN_DEADLINE, UNKNOWN_PUBLISH_TIME, infer_deadline_from_text,
    build_external_job_id, build_content_hash, SNAPSHOT_PREV, SNAPSHOT_LATEST, load_snapshot, save_snapshot
)
from parsers.company_registry import get_adapter

def parse_cdp_data():
    payloads = {}
    
    # Check old aggregated file
    try:
        with open("cdp_intercepted_payloads.json", "r", encoding="utf-8") as f:
            payloads.update(json.load(f))
    except FileNotFoundError:
        pass

    # Check new split files
    import glob
    for json_file in glob.glob("cdp_data/*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if k not in payloads:
                        payloads[k] = []
                    payloads[k].extend(v)
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    if not payloads:
        print("No CDP data found. Run cdp scrapers first.")
        return

    all_rows = []

    # 1. Xiaohongshu
    if "xiaohongshu" in payloads and payloads["xiaohongshu"]:
        adapter = get_adapter("xiaohongshu")
        for chunk in payloads["xiaohongshu"]:
            data = chunk.get("data", {})
            items = data.get("list", []) or data.get("records", [])
            for it in items:
                parsed = adapter.parse(it)
                if not parsed.get("title"): continue
                collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                raw_pub = normalize_time_value(parsed.get("publish_time") or parsed.get("update_time"))
                pub = raw_pub if is_time_like(raw_pub) else UNKNOWN_PUBLISH_TIME
                raw_ddl = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
                ddl = raw_ddl if is_time_like(raw_ddl) else UNKNOWN_DEADLINE
                all_rows.append({
                    "url": f"https://job.xiaohongshu.com/campus/position/{parsed.get('external_job_id')}" if parsed.get("external_job_id") else parsed.get("url", ""),
                    "company": "小红书",
                    "name": parsed.get("title", ""),
                    "city": parsed.get("city", ""),
                    "jd_raw": parsed.get("jd_raw", ""),
                    "publish_time": pub,
                    "deadline": ddl,
                    "collect_time": collect_ts,
                    "source": "official_xiaohongshu",
                    "recruit_type": parsed.get("recruit_type", ""),
                    "raw_tags": parsed.get("raw_tags", ""),
                    "external_job_id": parsed.get("external_job_id", ""),
                    "update_time": normalize_time_value(parsed.get("update_time", "")),
                    "publish_time_source": "real_api" if pub != UNKNOWN_PUBLISH_TIME else "unknown",
                    "deadline_source": "real_api_or_text" if ddl != UNKNOWN_DEADLINE else "unknown",
                })
        print(f"Parsed {len(payloads['xiaohongshu'])} chunks for Xiaohongshu")

    # 2. Bilibili
    if "bilibili" in payloads and payloads["bilibili"]:
        adapter = get_adapter("bilibili")
        for chunk in payloads["bilibili"]:
            data = chunk.get("data", {})
            items = data.get("list", []) or data.get("records", [])
            for it in items:
                parsed = adapter.parse(it)
                if not parsed.get("title"): continue
                collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                raw_pub = normalize_time_value(parsed.get("publish_time") or parsed.get("update_time"))
                pub = raw_pub if is_time_like(raw_pub) else UNKNOWN_PUBLISH_TIME
                raw_ddl = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
                ddl = raw_ddl if is_time_like(raw_ddl) else UNKNOWN_DEADLINE
                all_rows.append({
                    "url": f"https://jobs.bilibili.com/campus/position/detail?id={parsed.get('external_job_id')}" if parsed.get("external_job_id") else parsed.get("url", ""),
                    "company": "哔哩哔哩",
                    "name": parsed.get("title", ""),
                    "city": parsed.get("city", ""),
                    "jd_raw": parsed.get("jd_raw", ""),
                    "publish_time": pub,
                    "deadline": ddl,
                    "collect_time": collect_ts,
                    "source": "official_bilibili",
                    "recruit_type": parsed.get("recruit_type", ""),
                    "raw_tags": parsed.get("raw_tags", ""),
                    "external_job_id": parsed.get("external_job_id", ""),
                    "update_time": normalize_time_value(parsed.get("update_time", "")),
                    "publish_time_source": "real_api" if pub != UNKNOWN_PUBLISH_TIME else "unknown",
                    "deadline_source": "real_api_or_text" if ddl != UNKNOWN_DEADLINE else "unknown",
                })
        print(f"Parsed {len(payloads['bilibili'])} chunks for Bilibili")

    # 3. Tencent
    if "tencent" in payloads and payloads["tencent"]:
        for chunk in payloads["tencent"]:
            data = chunk.get("data", {})
            items = data.get("positionList", [])
            for it in items:
                title = norm(it.get("positionTitle") or it.get("position", ""))
                if not title: continue
                collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Tencent specific parsing
                city_list = it.get("workCities", [])
                city = ""
                if isinstance(city_list, list):
                    city = " ".join([c.get("cityName", "") if isinstance(c, dict) else str(c) for c in city_list])
                    
                jd_raw = norm(it.get("positionUrl", "")) # Often holds some detail or is missing. If list API doesn't have it, keep empty.
                bg_list = it.get("bgs", [])
                bg = ""
                if isinstance(bg_list, list) and bg_list:
                    bg = bg_list[0].get("bgName", "") if isinstance(bg_list[0], dict) else str(bg_list[0])
                
                tags = " ".join(filter(None, [bg, norm(it.get("positionFamily", ""))]))
                
                all_rows.append({
                    "url": f"https://join.qq.com/post.html?query=p_1&postId={it.get('postId', '')}",
                    "company": "腾讯",
                    "name": title,
                    "city": city,
                    "jd_raw": norm(it.get("positionRequirement", "") + " " + it.get("positionResponsibility", "") + " " + jd_raw),
                    "publish_time": UNKNOWN_PUBLISH_TIME,
                    "deadline": UNKNOWN_DEADLINE,
                    "collect_time": collect_ts,
                    "source": "official_tencent_api",
                    "recruit_type": norm(it.get("projectName", "") or it.get("recruitLabelName", "")),
                    "raw_tags": tags,
                    "external_job_id": str(it.get("postId", "")),
                    "update_time": "",
                    "publish_time_source": "unknown",
                    "deadline_source": "unknown",
                })
        print(f"Parsed {len(payloads['tencent'])} chunks for Tencent")

    # 4. Kuaishou
    if "kuaishou" in payloads and payloads["kuaishou"]:
        adapter = get_adapter("kuaishou")
        for chunk in payloads["kuaishou"]:
            result = chunk.get("result", {})
            items = result.get("list", []) or result.get("positions", []) or result.get("records", [])
            for it in items:
                parsed = adapter.parse(it)
                if not parsed.get("title"): continue
                collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                raw_pub = normalize_time_value(parsed.get("publish_time"))
                update_proxy = normalize_time_value(parsed.get("update_time"))
                pub = raw_pub if is_time_like(raw_pub) else (update_proxy if is_time_like(update_proxy) else UNKNOWN_PUBLISH_TIME)
                raw_ddl = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
                ddl = raw_ddl if is_time_like(raw_ddl) else UNKNOWN_DEADLINE
                all_rows.append({
                    "url": f"https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs/{parsed.get('external_job_id')}" if parsed.get("external_job_id") else parsed.get("url", ""),
                    "company": "快手",
                    "name": parsed.get("title", ""),
                    "city": parsed.get("city", ""),
                    "jd_raw": parsed.get("jd_raw", ""),
                    "publish_time": pub,
                    "deadline": ddl,
                    "collect_time": collect_ts,
                    "source": "official_kuaishou_api",
                    "recruit_type": parsed.get("recruit_type", ""),
                    "raw_tags": parsed.get("raw_tags", ""),
                    "external_job_id": parsed.get("external_job_id", ""),
                    "update_time": update_proxy,
                    "publish_time_source": "real_api" if is_time_like(raw_pub) else ("official_update_proxy" if is_time_like(update_proxy) else "unknown"),
                    "deadline_source": "real_api_or_text" if ddl != UNKNOWN_DEADLINE else "unknown",
                })
        print(f"Parsed {len(payloads['kuaishou'])} chunks for Kuaishou")

    # 5. Bytedance
    if "bytedance" in payloads and payloads["bytedance"]:
        for chunk in payloads["bytedance"]:
            data = chunk.get("data", {})
            items = data.get("post_data_list", [])
            for item in items:
                post = item.get("post", {})
                if not post: continue
                title = norm(post.get("name") or post.get("title"))
                if not title: continue
                city_list = item.get("city_list", [])
                city = " ".join([norm(c.get("name")) for c in city_list if c.get("name")])
                desc = norm(post.get("description", ""))
                req = norm(post.get("requirement", ""))
                pub_raw = normalize_time_value(post.get("publish_time"))
                collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                pid = norm(post.get("id"))
                all_rows.append({
                    "url": f"https://jobs.bytedance.com/campus/position/{pid}/detail" if pid else "",
                    "company": "字节跳动",
                    "name": title,
                    "city": city,
                    "jd_raw": norm(f"{desc} 岗位要求：{req}"),
                    "publish_time": pub_raw if is_time_like(pub_raw) else UNKNOWN_PUBLISH_TIME,
                    "deadline": UNKNOWN_DEADLINE,
                    "collect_time": collect_ts,
                    "source": "official_bytedance",
                    "recruit_type": norm(post.get("recruit_type", {}).get("name", "")),
                    "raw_tags": "",
                    "external_job_id": pid,
                    "update_time": normalize_time_value(post.get("update_time")),
                    "publish_time_source": "real_api" if is_time_like(pub_raw) else "unknown",
                    "deadline_source": "unknown"
                })
        print(f"Parsed {len(payloads['bytedance'])} chunks for Bytedance")

    # 6. Meituan
    if "meituan" in payloads and payloads["meituan"]:
        adapter = get_adapter("meituan")
        for chunk in payloads["meituan"]:
            data = chunk.get("data", {})
            items = data.get("list", [])
            for it in items:
                parsed = adapter.parse(it)
                if not parsed.get("title"): continue
                collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                raw_pub = normalize_time_value(parsed.get("publish_time") or parsed.get("update_time"))
                pub = raw_pub if is_time_like(raw_pub) else UNKNOWN_PUBLISH_TIME
                raw_ddl = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
                ddl = raw_ddl if is_time_like(raw_ddl) else UNKNOWN_DEADLINE
                all_rows.append({
                    "url": f"https://zhaopin.meituan.com/web/campus/detail?jobId={parsed.get('external_job_id')}" if parsed.get("external_job_id") else parsed.get("url", ""),
                    "company": "美团",
                    "name": parsed.get("title", ""),
                    "city": parsed.get("city", ""),
                    "jd_raw": parsed.get("jd_raw", ""),
                    "publish_time": pub,
                    "deadline": ddl,
                    "collect_time": collect_ts,
                    "source": "official_meituan",
                    "recruit_type": parsed.get("recruit_type", ""),
                    "raw_tags": parsed.get("raw_tags", ""),
                    "external_job_id": parsed.get("external_job_id", ""),
                    "update_time": normalize_time_value(parsed.get("update_time", "")),
                    "publish_time_source": "real_api" if pub != UNKNOWN_PUBLISH_TIME else "unknown",
                    "deadline_source": "real_api_or_text" if ddl != UNKNOWN_DEADLINE else "unknown",
                })
        print(f"Parsed {len(payloads['meituan'])} chunks for Meituan")

    # 6. Alibaba
    if "alibaba" in payloads and payloads["alibaba"]:
        for chunk in payloads["alibaba"]:
            # Check if this is our new DOM-extracted format
            if isinstance(chunk, dict) and "items" in chunk:
                items = chunk.get("items", [])
                for it in items:
                    title = norm(it.get("title"))
                    if not title: continue
                    
                    details = it.get("details", [])
                    pub = UNKNOWN_PUBLISH_TIME
                    city = ""
                    recruit_type = ""
                    
                    # Try to parse the array of details
                    # Usually: ["更新于 2026-03-18", "技术类", "北京 / 杭州", "在招业务", "阿里云"]
                    for d in details:
                        if "更新于" in d:
                            date_str = d.replace("更新于", "").strip()
                            pub = date_str if is_time_like(date_str) else UNKNOWN_PUBLISH_TIME
                        elif "类" in d and len(d) < 10:
                            recruit_type = norm(d)
                        elif "/" in d or "北京" in d or "上海" in d or "杭州" in d or "广州" in d or "深圳" in d or "成都" in d:
                            city = norm(d)
                    
                    job_url = it.get("url", "")
                    ali_id = ""
                    if job_url and "position/" in job_url:
                        ali_id = job_url.split("position/")[-1].split("?")[0]
                        
                    # Also try to extract department from the last detail if it exists
                    raw_tags = ""
                    if len(details) > 3 and "在招业务" in details[-2]:
                        raw_tags = norm(details[-1])
                        
                    all_rows.append({
                        "url": job_url,
                        "company": "阿里巴巴",
                        "name": title,
                        "city": city,
                        "jd_raw": norm(" ".join(details)), # Use details as JD since we can't click into each one easily without getting blocked
                        "publish_time": pub,
                        "deadline": UNKNOWN_DEADLINE,
                        "collect_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "official_ali_dom",
                        "recruit_type": recruit_type,
                        "raw_tags": raw_tags,
                        "external_job_id": ali_id,
                        "update_time": pub,
                        "publish_time_source": "real_api" if pub != UNKNOWN_PUBLISH_TIME else "unknown",
                        "deadline_source": "unknown",
                    })
            # Handle the old API-intercepted format just in case
            elif isinstance(chunk, dict) and "content" in chunk and "data" in chunk.get("content", {}):
                items = chunk["content"]["data"]
                adapter = get_adapter("alibaba")
                for it in items:
                    parsed = adapter.parse(it)
                    if not parsed.get("title"): continue
                    collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    raw_pub = normalize_time_value(parsed.get("publish_time") or parsed.get("update_time"))
                    pub = raw_pub if is_time_like(raw_pub) else UNKNOWN_PUBLISH_TIME
                    raw_ddl = normalize_time_value(parsed.get("deadline")) or infer_deadline_from_text(parsed.get("jd_raw", ""))
                    ddl = raw_ddl if is_time_like(raw_ddl) else UNKNOWN_DEADLINE
                    all_rows.append({
                        "url": f"https://talent.alibaba.com/position/{parsed.get('external_job_id')}" if parsed.get("external_job_id") else parsed.get("url", ""),
                        "company": "阿里巴巴",
                        "name": parsed.get("title", ""),
                        "city": parsed.get("city", ""),
                        "jd_raw": parsed.get("jd_raw", ""),
                        "publish_time": pub,
                        "deadline": ddl,
                        "collect_time": collect_ts,
                        "source": "official_ali_api",
                        "recruit_type": parsed.get("recruit_type", ""),
                        "raw_tags": parsed.get("raw_tags", ""),
                        "external_job_id": parsed.get("external_job_id", ""),
                        "update_time": normalize_time_value(parsed.get("update_time", "")),
                        "publish_time_source": "real_api" if pub != UNKNOWN_PUBLISH_TIME else "unknown",
                        "deadline_source": "real_api_or_text" if ddl != UNKNOWN_DEADLINE else "unknown",
                    })
        print(f"Parsed {len(payloads['alibaba'])} chunks for Alibaba")

    # 8. JD
    if "jd" in payloads and payloads["jd"]:
        for chunk in payloads["jd"]:
            data = chunk.get("body", {})
            items = data.get("items", []) or data.get("list", []) or data.get("records", [])
            for it in items:
                title = norm(it.get("positionName") or it.get("title"))
                if not title: continue
                
                # JD specific parsing
                collect_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                raw_pub = normalize_time_value(it.get("publishTime") or it.get("updateTime"))
                pub = raw_pub if is_time_like(raw_pub) else UNKNOWN_PUBLISH_TIME
                raw_ddl = normalize_time_value(it.get("deadline")) or infer_deadline_from_text(it.get("workContent", ""))
                ddl = raw_ddl if is_time_like(raw_ddl) else UNKNOWN_DEADLINE
                
                city = norm(it.get("workCity", ""))
                jd_id = it.get("publishId") or it.get("reqId") or it.get("id")
                
                jd_raw = norm(it.get("workContent", "") + " " + it.get("qualification", ""))
                
                all_rows.append({
                    "url": f"https://campus.jd.com/#/jobs/{jd_id}" if jd_id else "",
                    "company": "京东",
                    "name": title,
                    "city": city,
                    "jd_raw": jd_raw,
                    "publish_time": pub,
                    "deadline": ddl,
                    "collect_time": collect_ts,
                    "source": "official_jd_api",
                    "recruit_type": norm(it.get("positionTypeName", "")),
                    "raw_tags": norm(it.get("jobCategory", "") + " " + it.get("jobDirection", "")),
                    "external_job_id": str(jd_id),
                    "update_time": normalize_time_value(it.get("updateTime", "")),
                    "publish_time_source": "real_api" if pub != UNKNOWN_PUBLISH_TIME else "unknown",
                    "deadline_source": "real_api_or_text" if ddl != UNKNOWN_DEADLINE else "unknown",
                })
        print(f"Parsed {len(payloads['jd'])} chunks for JD")

    # Dedup and Merge
    if not all_rows:
        print("No valid rows parsed from CDP data.")
        return

    new_df = pd.DataFrame(all_rows)
    for col in ["salary", "company_size", "duration", "academic"]:
        if col not in new_df.columns:
            new_df[col] = ""
    new_df = new_df.fillna("")

    new_df["external_job_id"] = new_df.apply(lambda r: build_external_job_id(r.to_dict()), axis=1)
    new_df["content_hash"] = new_df.apply(lambda r: build_content_hash(r.to_dict()), axis=1)
    new_df["sync_key"] = new_df["source"].astype(str) + "|" + new_df["external_job_id"].astype(str)
    new_df = new_df.drop_duplicates(subset=["company", "name", "city", "url", "jd_raw"], keep="first")

    print(f"Total deduplicated rows from CDP: {len(new_df)}")

    # Load existing official_jobs_raw.csv to append/update
    existing_file = "official_jobs_raw.csv"
    try:
        old_df = pd.read_csv(existing_file, keep_default_na=False)
        old_df["sync_key"] = old_df["source"].astype(str) + "|" + old_df["external_job_id"].astype(str)
        # We will update rows where sync_key matches, and append new ones
        merged_df = pd.concat([new_df, old_df[~old_df["sync_key"].isin(new_df["sync_key"])]], ignore_index=True)
        print(f"Merged with existing data. Old size: {len(old_df)}, New size: {len(merged_df)}")
    except FileNotFoundError:
        merged_df = new_df
        print("No existing official_jobs_raw.csv found, creating new one.")

    # Sort to keep things tidy
    merged_df = merged_df.sort_values(by=["company", "publish_time"], ascending=[True, False])
    
    # Save
    cols_to_save = ["url", "company", "name", "city", "jd_raw", "salary", "company_size", "duration", "academic", "publish_time", "deadline", "collect_time", "source", "recruit_type", "raw_tags", "external_job_id", "update_time", "publish_time_source", "deadline_source"]
    # Ensure all columns exist
    for c in cols_to_save:
        if c not in merged_df.columns:
            merged_df[c] = ""

    merged_df[cols_to_save].to_csv(existing_file, index=False, encoding="utf-8-sig")
    print(f"Successfully saved {len(merged_df)} rows to {existing_file}")

if __name__ == "__main__":
    parse_cdp_data()