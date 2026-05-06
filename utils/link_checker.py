import asyncio
from typing import Dict, List
from urllib.parse import urlparse

import requests


def _is_http_url(url: str) -> bool:
    try:
        p = urlparse(str(url).strip())
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def _do_check(url: str, timeout: int = 6) -> Dict[str, str]:
    status = "UNKNOWN"
    reason = ""
    if not _is_http_url(url):
        return {"url": url, "status": "RISKY", "reason": "Invalid URL"}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        code = int(resp.status_code)
        if code == 200:
            return {"url": url, "status": "OK", "reason": ""}
        if code == 404:
            return {"url": url, "status": "BROKEN", "reason": "404 Not Found"}
        resp_get = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers, stream=True)
        content = ""
        try:
            raw = next(resp_get.iter_content(chunk_size=1200), b"")
            content = raw.decode("utf-8", errors="ignore")
        except Exception:
            content = ""
        low = content.lower()
        if any(x in low for x in ["岗位已下线", "页面不存在", "该职位已结束", "page not found", "not found"]):
            status = "BROKEN"
            reason = "Content indicates offline"
        elif int(resp_get.status_code) == 200:
            status = "OK"
            reason = ""
        else:
            status = "RISKY"
            reason = f"Status {resp_get.status_code}"
    except requests.Timeout:
        status = "RISKY"
        reason = "Timeout"
    except Exception as e:
        status = "RISKY"
        reason = str(e)[:80]
    return {"url": url, "status": status, "reason": reason}


async def check_single_link(url: str, timeout: int = 6, semaphore: asyncio.Semaphore | None = None) -> Dict[str, str]:
    if semaphore is None:
        semaphore = asyncio.Semaphore(10)
    async with semaphore:
        return await asyncio.to_thread(_do_check, url, timeout)


async def check_links_batch(urls: List[str], max_concurrent: int = 10, timeout: int = 6) -> List[Dict[str, str]]:
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [check_single_link(url, timeout=timeout, semaphore=semaphore) for url in urls]
    return await asyncio.gather(*tasks)
