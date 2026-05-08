"""DeepSeek-powered resume-job matching engine."""
import os
import json
import requests
from typing import Dict, List

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/chat/completions"

_HEADERS = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}

_SYSTEM_PROMPT = """你是一个专业的简历匹配分析助手。你的任务：
1. 分析求职者简历中的技能、经验、学历
2. 对比岗位需求，给出匹配度评分（0-100）
3. 明确指出匹配点和不匹配点
4. 输出格式严格如下，不要多余内容：

{
  "score": 85,
  "reason": "简历中3段数据分析实习经验与岗位高度匹配，SQL/Python/Tableau均符合要求；缺少AB测试经验",
  "hit_skills": ["Python", "SQL", "数据分析"],
  "gap_skills": ["AB测试"]
}"""


def _call_deepseek(resume: str, job_title: str, jd: str) -> Dict:
    """Score one resume-job pair via DeepSeek."""
    if not DEEPSEEK_KEY:
        return {"score": 50, "reason": "API key not configured", "hit_skills": [], "gap_skills": []}

    user_prompt = f"""## 简历
{resume[:1500]}

## 岗位
标题：{job_title}
描述：{jd[:2000]}"""

    try:
        resp = requests.post(
            API_URL,
            headers=_HEADERS,
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            timeout=30,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Parse JSON from response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
        result = json.loads(content)
        return {
            "score": min(100, max(0, int(result.get("score", 50)))),
            "reason": result.get("reason", "")[:200],
            "hit_skills": result.get("hit_skills", []),
            "gap_skills": result.get("gap_skills", []),
        }
    except Exception as e:
        return {"score": 50, "reason": f"LLM评估异常: {str(e)[:50]}", "hit_skills": [], "gap_skills": []}


def match(resume: str, jobs: List[Dict], top_n: int = 20) -> List[Dict]:
    """Keyword pre-filter then LLM re-rank."""
    resume_lower = resume.lower()
    resume_words = set(resume_lower.split())

    # Step 1: keyword pre-filter (free)
    scored = []
    for job in jobs:
        jd = f"{job.get('title', '')} {job.get('jd_raw', '')}".lower()
        kw_score = sum(1 for w in resume_words if w in jd and len(w) > 3)
        if kw_score > 0:
            scored.append((kw_score, job))

    scored.sort(key=lambda x: x[0], reverse=True)
    candidates = [job for _, job in scored[:60]]

    # Step 2: LLM re-rank (paid)
    results = []
    for job in candidates:
        llm = _call_deepseek(resume, job.get("title", ""), job.get("jd_raw", ""))
        results.append({
            **job,
            "match_score": llm["score"],
            "match_reason": llm["reason"],
            "hit_skills": llm["hit_skills"],
            "gap_skills": llm["gap_skills"],
        })

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:top_n]
