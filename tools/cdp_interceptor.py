"""
cdp_interceptor.py — BilalAgent v2.0 CDP Network Interception
Uses Playwright CDP to intercept LinkedIn's internal job API calls.
Extracts richer data (salary, skills, applicant count) than HTML scraping.
Falls back to JobSpy if CDP fails.
"""

import json
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def intercept_linkedin_jobs(search_query: str, max_jobs: int = 20) -> list:
    """
    Use CDP to intercept LinkedIn's internal Voyager API for rich job data.
    
    LinkedIn's frontend fetches job data via internal API calls containing
    'voyagerJobsDashJobCards' or 'jobPostings' in the URL. These return
    clean JSON with salary, skills, and applicant count — data not always
    visible in the HTML.
    
    Args:
        search_query: Job search query (e.g. "AI Engineer remote")
        max_jobs: Maximum number of jobs to capture
        
    Returns:
        List of enriched job dicts, or empty list if CDP fails
    """
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
    except ImportError:
        print("[CDP] playwright or playwright-stealth not installed")
        return []
    
    print(f"[CDP] Intercepting LinkedIn API for: '{search_query}'...")
    
    captured_responses = []
    jobs = []
    stealth = Stealth()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            
            page = context.new_page()
            stealth.apply_stealth(page)
            
            # Intercept network responses
            def handle_response(response):
                url = response.url
                if any(keyword in url for keyword in [
                    "voyagerJobsDashJobCards",
                    "jobPostings",
                    "voyagerJobsDashJobPostings",
                    "jobs/search",
                ]):
                    try:
                        body = response.json()
                        captured_responses.append({
                            "url": url,
                            "data": body,
                            "status": response.status,
                        })
                        print(f"[CDP] Captured API response: {url[:80]}...")
                    except Exception:
                        pass
            
            page.on("response", handle_response)
            
            # Navigate to LinkedIn job search
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_query.replace(' ', '%20')}&location=Worldwide&f_WT=2"
            print(f"[CDP] Navigating to LinkedIn jobs...")
            
            page.goto(search_url, wait_until="networkidle", timeout=30000)
            
            # Scroll to trigger lazy-loading of more results
            for i in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
            
            # Wait a bit for remaining API calls
            time.sleep(2)
            
            browser.close()
        
        # Parse captured API responses
        if captured_responses:
            jobs = _parse_voyager_responses(captured_responses, max_jobs)
            print(f"[CDP] Extracted {len(jobs)} enriched jobs from LinkedIn API")
        else:
            print("[CDP] No API responses captured (may need LinkedIn login)")
        
        return jobs
        
    except Exception as e:
        print(f"[CDP] Interception failed: {e}")
        return []


def _parse_voyager_responses(responses: list, max_jobs: int) -> list:
    """Parse LinkedIn's Voyager API responses into clean job dicts."""
    jobs = []
    seen_ids = set()
    
    for resp in responses:
        data = resp.get("data", {})
        
        # LinkedIn nests data in various structures
        elements = []
        
        # Try different response formats
        if isinstance(data, dict):
            # Format 1: included array
            elements.extend(data.get("included", []))
            # Format 2: data.elements
            if "data" in data and isinstance(data["data"], dict):
                elements.extend(data["data"].get("elements", []))
                # Nested paging
                paging_data = data["data"].get("paging", {})
                elements.extend(data["data"].get("*elements", []))
        
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            
            # Filter for job posting entities
            entity_type = elem.get("$type", "")
            if "JobPosting" not in entity_type and "title" not in elem:
                continue
            
            job_id = elem.get("entityUrn", elem.get("trackingUrn", ""))
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            
            job = {
                "title": elem.get("title", elem.get("jobPostingTitle", "")),
                "company": _extract_company(elem),
                "location": elem.get("formattedLocation", elem.get("location", "")),
                "url": _build_job_url(elem),
                "description": elem.get("description", {}).get("text", "")[:2000] if isinstance(elem.get("description"), dict) else str(elem.get("description", ""))[:2000],
                "salary": _extract_salary(elem),
                "site_name": "linkedin_cdp",
                "date_posted": elem.get("listedAt", elem.get("formattedDate", "")),
                # CDP-exclusive enriched fields
                "applicant_count": elem.get("applies", elem.get("numApplicants", None)),
                "seniority_level": elem.get("formattedExperienceLevel", ""),
                "employment_type": elem.get("formattedEmploymentStatus", elem.get("employmentType", "")),
                "skills": _extract_skills(elem),
            }
            
            if job["title"]:
                jobs.append(job)
                if len(jobs) >= max_jobs:
                    break
        
        if len(jobs) >= max_jobs:
            break
    
    return jobs


def _extract_company(elem: dict) -> str:
    """Extract company name from various LinkedIn API formats."""
    company = elem.get("companyDetails", {})
    if isinstance(company, dict):
        comp = company.get("company", company.get("*companyResolutionResult", ""))
        if isinstance(comp, dict):
            return comp.get("name", "")
        return str(comp) if comp else ""
    return elem.get("companyName", str(company) if company else "")


def _extract_salary(elem: dict) -> str:
    """Extract salary from LinkedIn's compensation data."""
    comp = elem.get("salaryInsights", elem.get("compensationInfo", {}))
    if isinstance(comp, dict):
        base = comp.get("baseSalary", comp.get("compensationRange", {}))
        if isinstance(base, dict):
            min_val = base.get("from", base.get("min", {}).get("amount", None))
            max_val = base.get("to", base.get("max", {}).get("amount", None))
            if min_val and max_val:
                return f"${min_val:,.0f}-${max_val:,.0f}/yr"
            elif min_val:
                return f"${min_val:,.0f}+/yr"
    
    formatted = elem.get("formattedSalary", "")
    return formatted if formatted else "Not listed"


def _extract_skills(elem: dict) -> list:
    """Extract required skills from job posting."""
    skills = []
    skill_data = elem.get("skillMatchStatuses", elem.get("jobPostingSkills", []))
    if isinstance(skill_data, list):
        for s in skill_data:
            if isinstance(s, dict):
                name = s.get("skill", {}).get("name", s.get("localizedSkillDisplayName", ""))
                if name:
                    skills.append(name)
            elif isinstance(s, str):
                skills.append(s)
    return skills[:15]


def _build_job_url(elem: dict) -> str:
    """Build a viewable LinkedIn job URL from entity data."""
    urn = elem.get("entityUrn", "")
    if "jobPosting" in urn.lower():
        job_id = urn.split(":")[-1]
        return f"https://www.linkedin.com/jobs/view/{job_id}/"
    
    tracking = elem.get("jobPostingId", elem.get("trackingUrn", ""))
    if tracking:
        job_id = str(tracking).split(":")[-1]
        return f"https://www.linkedin.com/jobs/view/{job_id}/"
    
    return ""


if __name__ == "__main__":
    print("=" * 50)
    print("CDP Interceptor Test")
    print("=" * 50)
    jobs = intercept_linkedin_jobs("AI Engineer", max_jobs=5)
    for i, j in enumerate(jobs[:5], 1):
        print(f"\n{i}. {j['title']} @ {j['company']}")
        print(f"   {j['location']} | {j['salary']}")
        print(f"   Skills: {', '.join(j.get('skills', []))}")
        print(f"   Applicants: {j.get('applicant_count', 'N/A')}")
