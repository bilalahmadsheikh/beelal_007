"""
job_tools.py — BilalAgent v2.0 Job Scoring & Filtering
Scores jobs against user profile using gemma3:1b for fast evaluation.
Profile skills loaded dynamically from profile.yaml.
"""

import sys
import os
import yaml
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_runner import safe_run, get_free_ram


# In-memory cache so we don't read profile.yaml on every score_job() call
_profile_cache = None


def _load_profile_info() -> dict:
    """Load key profile info for scoring context, cached in memory."""
    global _profile_cache
    if _profile_cache is not None:
        return _profile_cache
    
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "profile.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = yaml.safe_load(f) or {}
        personal = profile.get("personal", {})
        projects = profile.get("projects", [])
        _profile_cache = {
            "name": personal.get("name", ""),
            "degree": personal.get("degree", ""),
            "skills": personal.get("skills", []),
            "project_names": [p.get("name", "") for p in projects],
            "project_techs": list(set(
                tech for p in projects 
                for tech in p.get("tech_stack", [])
            )),
        }
    except Exception:
        _profile_cache = {"skills": [], "project_names": [], "project_techs": []}
    return _profile_cache


SCORING_SYSTEM_PROMPT = """You are a job-match scoring engine. Given a job posting and a candidate's profile, output ONLY a JSON object with these exact keys:

- "score": integer 0-100 (how well the candidate matches)
- "matching_skills": list of skills the candidate HAS that match the job
- "missing": list of skills the job REQUIRES that the candidate LACKS
- "reason": one sentence explaining the score

Score guidelines:
- 90-100: Perfect match, candidate has all required skills + relevant projects
- 70-89: Strong match, most skills aligned, minor gaps
- 50-69: Partial match, some skills but significant gaps
- 30-49: Weak match, few overlapping skills
- 0-29: Poor match, very different skill set

Output ONLY the JSON. No explanation, no markdown."""


def score_job(job: dict) -> dict:
    """
    Score a job against the user's profile using gemma3:1b.
    
    Args:
        job: Job dict with title, company, description, etc.
        
    Returns:
        dict with score, matching_skills, missing, reason
    """
    profile = _load_profile_info()
    
    # Build a concise prompt (keep it small for 1B model)
    description_snippet = job.get("description", "")[:800]
    
    prompt = f"""Score this job match:

JOB: {job.get('title', '')} at {job.get('company', '')}
Description: {description_snippet}
Salary: {job.get('salary', 'N/A')}

CANDIDATE SKILLS: {', '.join(profile['skills'])}
CANDIDATE PROJECTS: {', '.join(profile['project_names'])}
CANDIDATE TECH: {', '.join(profile['project_techs'])}
CANDIDATE: {profile.get('degree', '')}

Output JSON: {{"score": int, "matching_skills": list, "missing": list, "reason": str}}"""
    
    # Load scoring model from settings
    try:
        import yaml as _yaml
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.yaml")
        with open(settings_path, "r") as f:
            scoring_model = (_yaml.safe_load(f) or {}).get("routing_model", "gemma3:1b")
    except Exception:
        scoring_model = "gemma3:1b"
    
    raw = safe_run(scoring_model, prompt, required_gb=0.5, system=SCORING_SYSTEM_PROMPT)
    
    if raw.startswith("[ERROR]"):
        return _fallback_score(job, profile)
    
    return _parse_score(raw, job, profile)


def _parse_score(raw: str, job: dict, profile: dict) -> dict:
    """Parse scoring JSON from model output."""
    text = raw.strip()
    
    # Strip markdown fences
    if "```" in text:
        lines = text.split("\n")
        json_lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(json_lines).strip()
    
    # Find JSON
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    
    try:
        result = json.loads(text)
        # Validate and clamp score
        score = max(0, min(100, int(result.get("score", 0))))
        return {
            "score": score,
            "matching_skills": result.get("matching_skills", []),
            "missing": result.get("missing", []),
            "reason": result.get("reason", ""),
            "job_title": job.get("title", ""),
            "company": job.get("company", ""),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return _fallback_score(job, profile)


def _fallback_score(job: dict, profile: dict) -> dict:
    """Simple keyword-based scoring when model fails."""
    skills = [s.lower() for s in profile.get("skills", [])]
    techs = [t.lower() for t in profile.get("project_techs", [])]
    all_candidate = set(skills + techs)
    
    desc_lower = (job.get("description", "") + " " + job.get("title", "")).lower()
    
    matching = [s for s in all_candidate if s in desc_lower]
    score = min(100, len(matching) * 15)  # ~15 points per match
    
    return {
        "score": score,
        "matching_skills": matching,
        "missing": [],
        "reason": f"Keyword match: {len(matching)} skills found in description",
        "job_title": job.get("title", ""),
        "company": job.get("company", ""),
    }


def get_top_jobs(jobs: list, min_score: int = 65) -> list:
    """
    Score all jobs and return those above min_score, sorted by score descending.
    
    Args:
        jobs: List of job dicts
        min_score: Minimum score to include (default 65)
        
    Returns:
        List of (job, score_result) tuples sorted by score
    """
    scored = []
    total = len(jobs)
    
    for i, job in enumerate(jobs, 1):
        print(f"  [SCORING] {i}/{total}: {job.get('title', '')} @ {job.get('company', '')}...")
        score_result = score_job(job)
        scored.append((job, score_result))
    
    # Filter and sort
    filtered = [(j, s) for j, s in scored if s["score"] >= min_score]
    filtered.sort(key=lambda x: x[1]["score"], reverse=True)
    
    return filtered


def display_jobs(scored_jobs: list, limit: int = 5) -> str:
    """Format scored jobs for display."""
    lines = []
    for i, (job, score) in enumerate(scored_jobs[:limit], 1):
        lines.append(f"\n{'─' * 50}")
        lines.append(f"  #{i} | Score: {score['score']}/100")
        lines.append(f"  {job['title']} @ {job['company']}")
        lines.append(f"  📍 {job['location']} | 💰 {job['salary']}")
        lines.append(f"  🔗 {job['url'][:70]}")
        lines.append(f"  ✅ Matching: {', '.join(score['matching_skills'][:5])}")
        if score['missing']:
            lines.append(f"  ❌ Missing: {', '.join(score['missing'][:3])}")
        lines.append(f"  📝 {score['reason']}")
        lines.append(f"  📰 Source: {job.get('site_name', 'unknown')}")
    
    lines.append(f"\n{'─' * 50}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 50)
    print("Job Tools Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 50)
    
    test_job = {
        "title": "Python AI Engineer",
        "company": "TechCorp",
        "description": "Looking for Python developer with FastAPI, MLOps, Docker experience. ML pipeline development.",
        "salary": "$120,000-$160,000/yr",
        "location": "Remote",
        "url": "https://example.com/job/123",
    }
    
    result = score_job(test_job)
    print(f"\nScore: {result['score']}/100")
    print(f"Matching: {result['matching_skills']}")
    print(f"Missing: {result['missing']}")
    print(f"Reason: {result['reason']}")
