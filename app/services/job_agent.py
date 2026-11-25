import html
import json
import re
from urllib.request import Request, urlopen
from urllib.parse import quote

from app.models.profile import Profile
from app.models.resume import Resume
from app.core.config import settings


SOURCES = (
    ("Remotive", "https://remotive.com/api/remote-jobs"),
    ("Arbeitnow", "https://www.arbeitnow.com/api/job-board-api"),
)
ROLE_GENERIC_TERMS = {
    "developer", "engineer", "junior", "lead", "mid", "principal", "senior",
    "staff",
}


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "AI-Job-Application-Agent/1.0"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean_html(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_jobs() -> tuple[list[dict], list[str]]:
    jobs: list[dict] = []
    errors: list[str] = []

    for platform, url in SOURCES:
        try:
            payload = _get_json(url)
        except Exception as error:
            errors.append(f"{platform}: {error}")
            continue

        source_jobs = payload.get("jobs", []) if platform == "Remotive" else payload.get("data", [])
        for item in source_jobs:
            if platform == "Remotive":
                job = {
                    "source_job_id": str(item.get("id") or ""),
                    "title": item.get("title", ""),
                    "company": item.get("company_name", ""),
                    "location": item.get("candidate_required_location", ""),
                    "description": _clean_html(item.get("description")),
                    "application_url": item.get("url"),
                    "platform": platform,
                }
            else:
                job = {
                    "source_job_id": str(item.get("slug") or ""),
                    "title": item.get("title", ""),
                    "company": item.get("company_name", ""),
                    "location": item.get("location", ""),
                    "description": _clean_html(item.get("description")),
                    "application_url": item.get("url"),
                    "platform": platform,
                }

            if job["source_job_id"] and job["title"] and job["application_url"]:
                jobs.append(job)

    if settings.greenhouse_board_token:
        board_token = quote(settings.greenhouse_board_token.strip(), safe="")
        greenhouse_url = (
            f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        )
        try:
            payload = _get_json(greenhouse_url)
        except Exception as error:
            errors.append(f"Greenhouse: {error}")
        else:
            for item in payload.get("jobs", []):
                location = item.get("location")
                jobs.append({
                    "source_job_id": str(item.get("id") or ""),
                    "title": item.get("title", ""),
                    "company": item.get("company_name") or settings.greenhouse_board_token,
                    "location": location.get("name", "") if isinstance(location, dict) else "",
                    "description": _clean_html(item.get("content")),
                    "application_url": item.get("absolute_url"),
                    "platform": "Greenhouse",
                })

    jobs = [
        job for job in jobs
        if job["source_job_id"] and job["title"] and job["application_url"]
    ]
    return jobs, errors


def _tokens(value: str | None) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9+#.]+", (value or "").lower())
        if len(token) > 2
    }


def _resume_terms(resume: Resume) -> set[str]:
    analysis = resume.analysis_json or {}
    terms: set[str] = set()
    for key in ("skills", "technologies", "certifications", "recommended_roles"):
        values = analysis.get(key, [])
        if isinstance(values, list):
            terms.update(_tokens(" ".join(str(value) for value in values)))
    if not terms and resume.extracted_text:
        terms = _tokens(resume.extracted_text)
    return terms


def _profile_terms(profile: Profile | None) -> set[str]:
    if profile is None:
        return set()
    return _tokens(
        f"{profile.preferred_roles or ''} {profile.preferred_locations or ''} "
        f"{profile.experience or ''} {profile.education or ''}"
    )


def _required_years(value: str | None) -> float | None:
    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:years?|yrs?)",
        value or "",
        flags=re.IGNORECASE,
    )
    return max((float(match) for match in matches), default=None)


def _candidate_years(profile: Profile | None, resume: Resume) -> float | None:
    values = [profile.experience if profile else "", resume.extracted_text or ""]
    analysis = resume.analysis_json or {}
    values.append(" ".join(str(x) for x in analysis.get("experience", [])))
    return max(
        (years for value in values if (years := _required_years(value)) is not None),
        default=None,
    )


def _role_match(job: dict, profile: Profile | None, resume: Resume) -> bool:
    role_terms = set()
    if profile:
        role_terms |= _tokens(profile.preferred_roles)
    role_terms |= _tokens(
        " ".join(resume.analysis_json.get("recommended_roles", []))
        if resume.analysis_json
        else ""
    )
    role_terms -= ROLE_GENERIC_TERMS
    title_terms = _tokens(job["title"]) - ROLE_GENERIC_TERMS
    return bool(title_terms & role_terms) if role_terms else True


def _location_match(job: dict, profile: Profile | None) -> bool:
    if not profile or not profile.preferred_locations:
        return True
    wanted = _tokens(profile.preferred_locations)
    location = _tokens(job.get("location"))
    return not location or bool(wanted & location) or "remote" in wanted or "remote" in location


def match_job(job: dict, profile: Profile | None, resumes: list[Resume]) -> dict:
    job_terms = _tokens(f"{job['title']} {job['location']} {job['description']}")
    profile_terms = _profile_terms(profile)
    best = None

    for resume in resumes:
        resume_terms = _resume_terms(resume)
        keyword_matches = (job_terms & (resume_terms | profile_terms)) - ROLE_GENERIC_TERMS
        role_ok = _role_match(job, profile, resume)
        location_ok = _location_match(job, profile)
        required_years = _required_years(f"{job['title']} {job['description']}")
        candidate_years = _candidate_years(profile, resume)
        experience_ok = (
            required_years is None
            or candidate_years is None
            or candidate_years >= required_years
        )

        if not role_ok or not experience_ok:
            continue

        matchable_job_terms = job_terms - ROLE_GENERIC_TERMS
        keyword_score = (
            70.0 * len(keyword_matches) / len(matchable_job_terms)
            if matchable_job_terms
            else 0.0
        )
        role_score = 20.0 if role_ok else 0.0
        location_score = 10.0 if location_ok else 0.0
        experience_score = 10.0 if required_years is not None and candidate_years is not None else 0.0
        score = min(100.0, keyword_score + role_score + location_score + experience_score)

        if best is None or score > best["score"]:
            best = {
                "score": round(score, 1),
                "resume": resume,
                "matched_terms": sorted(keyword_matches)[:25],
            }

    return best or {
        "score": 0.0,
        "resume": None,
        "matched_terms": [],
    }


def discover_and_match(profile: Profile | None, resumes: list[Resume]) -> tuple[list[dict], list[str]]:
    source_jobs, errors = fetch_jobs()
    recommendations: list[dict] = []

    for source_job in source_jobs:
        match = match_job(source_job, profile, resumes)
        if match["resume"] is not None and match["score"] > 0:
            recommendations.append({
                "job": source_job,
                "score": match["score"],
                "matched_terms": match["matched_terms"],
                "resume": match["resume"],
            })

    recommendations.sort(key=lambda item: item["score"], reverse=True)
    return recommendations[:20], errors
