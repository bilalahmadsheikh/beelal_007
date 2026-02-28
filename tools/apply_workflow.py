"""
apply_workflow.py — BilalAgent v2.0 Job Application Workflow
Full pipeline: search → CDP enrich → score → display → approve → cover letter → log
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.jobspy_connector import search_jobs
from tools.cdp_interceptor import intercept_linkedin_jobs
from tools.job_tools import score_job, get_top_jobs, display_jobs
from memory.excel_logger import log_application, get_applications, display_applications


def run_job_search(query: str, location: str = "remote", num: int = 20, min_score: int = 65) -> str:
    """
    Full job search pipeline: search across sites → score against profile → display top results.
    
    Args:
        query: Job search query (e.g. "AI Engineer", "Python Developer")
        location: Location filter
        num: Number of results to fetch
        min_score: Minimum score to show
        
    Returns:
        Formatted string with top scored jobs
    """
    print(f"\n[JOBS] Starting job search: '{query}' in '{location}'")
    
    all_jobs = []
    cdp_used = False
    
    # Step 1: Try CDP interception for LinkedIn (enriched data)
    print("\n[JOBS] Step 1: Attempting LinkedIn CDP interception...")
    try:
        cdp_jobs = intercept_linkedin_jobs(query, max_jobs=10)
        if cdp_jobs:
            all_jobs.extend(cdp_jobs)
            cdp_used = True
            print(f"[JOBS] ✅ CDP captured {len(cdp_jobs)} enriched LinkedIn jobs")
        else:
            print("[JOBS] ⚠️ CDP returned no results (falling back to JobSpy for LinkedIn)")
    except Exception as e:
        print(f"[JOBS] ⚠️ CDP failed: {e} (falling back to JobSpy)")
    
    # Step 2: JobSpy for Indeed + Glassdoor (and LinkedIn if CDP failed)
    print("\n[JOBS] Step 2: Running JobSpy search...")
    try:
        jobspy_results = search_jobs(query, location, num)
        
        # Deduplicate: don't add LinkedIn jobs from JobSpy if CDP got them
        if cdp_used:
            jobspy_filtered = [j for j in jobspy_results if j.get("site_name") != "linkedin"]
            print(f"[JOBS] Added {len(jobspy_filtered)} jobs from Indeed/Glassdoor (LinkedIn via CDP)")
        else:
            jobspy_filtered = jobspy_results
            print(f"[JOBS] Added {len(jobspy_filtered)} jobs from all sites")
        
        all_jobs.extend(jobspy_filtered)
    except Exception as e:
        print(f"[JOBS] JobSpy error: {e}")
    
    if not all_jobs:
        return "[JOBS] No jobs found. Try a different search query or check your internet connection."
    
    # Step 3: Score all jobs against profile
    print(f"\n[JOBS] Step 3: Scoring {len(all_jobs)} jobs against your profile...")
    top = get_top_jobs(all_jobs, min_score=min_score)
    
    if not top:
        # Show top 5 regardless of score
        print(f"[JOBS] No jobs scored above {min_score}. Showing top 5 by score...")
        all_scored = []
        for job in all_jobs[:10]:
            s = score_job(job)
            all_scored.append((job, s))
        all_scored.sort(key=lambda x: x[1]["score"], reverse=True)
        top = all_scored[:5]
    
    # Step 4: Display results
    result_lines = []
    result_lines.append(f"\n🔍 Job Search Results: '{query}' in '{location}'")
    result_lines.append(f"{'═' * 50}")
    result_lines.append(f"Sources: {'CDP + JobSpy' if cdp_used else 'JobSpy'}")
    result_lines.append(f"Total found: {len(all_jobs)} | Above {min_score}: {len(top)}")
    result_lines.append(display_jobs(top, limit=5))
    
    # Log top jobs as "saved"
    for job, score in top[:5]:
        log_application(job, score, status="saved")
    
    return "\n".join(result_lines)


def run_apply_flow(job: dict, score_result: dict) -> str:
    """
    Full application flow for a single job:
    1. Generate cover letter using content tools
    2. Show for approval
    3. Save to cover_letters/
    4. Log to Excel
    
    Args:
        job: Job dict
        score_result: Score dict from score_job()
        
    Returns:
        Status message
    """
    from tools.content_tools import generate_cover_letter
    from ui.approval_cli import show_approval
    
    company = job.get("company", "Unknown")
    title = job.get("title", "Unknown")
    description = job.get("description", "")[:1000]
    
    print(f"\n[APPLY] Generating cover letter for: {title} at {company}")
    
    # Generate cover letter with job context
    cover_letter = generate_cover_letter(
        job_title=title,
        company=company,
        job_description=description,
        user_request=f"Apply for {title} at {company}. Match my skills to this job."
    )
    
    if cover_letter.startswith("[ERROR]"):
        return f"[APPLY] Failed to generate cover letter: {cover_letter}"
    
    # Show for approval
    approval = show_approval("cover_letter", cover_letter)
    
    if approval is None:
        log_application(job, score_result, status="cancelled")
        return "[APPLY] Application cancelled."
    
    # Use approved/edited content
    final_letter = approval if approval != "approved" else cover_letter
    
    # Save cover letter to file
    cover_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "memory", "cover_letters")
    os.makedirs(cover_dir, exist_ok=True)
    
    safe_company = "".join(c for c in company if c.isalnum() or c in " _-").strip().replace(" ", "_")
    filename = f"{datetime.now().strftime('%Y%m%d')}_{safe_company}_{title[:30].replace(' ', '_')}.txt"
    filepath = os.path.join(cover_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Cover Letter for {title} at {company}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Score: {score_result.get('score', 0)}/100\n")
        f.write(f"{'─' * 50}\n\n")
        f.write(final_letter)
    
    print(f"[APPLY] Cover letter saved: {filepath}")
    
    # Log to Excel
    log_application(job, score_result, status="applied", cover_letter_path=filepath)
    
    return f"[APPLY] ✅ Applied to {title} at {company} (Score: {score_result.get('score', 0)}). Cover letter saved."


def show_my_applications(status: str = None) -> str:
    """Show logged applications from Excel."""
    apps = get_applications(status)
    return display_applications(apps)


if __name__ == "__main__":
    print("=" * 50)
    print("Apply Workflow Test")
    print("=" * 50)
    
    result = run_job_search("AI Engineer", "remote", num=5, min_score=50)
    print(result)
