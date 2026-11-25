import json
import re
from pathlib import Path

import httpx
from docx import Document
from fastapi import HTTPException
from google import genai
from google.genai.errors import APIError
from pypdf import PdfReader

from app.core.config import settings


SKILL_CATALOG = [
    "python", "java", "c", "c++", "javascript", "typescript", "sql",
    "html", "css", "react", "angular", "vue", "django", "flask", "fastapi",
    "node.js", "express", "postgresql", "mysql", "mongodb", "redis",
    "git", "github", "docker", "kubernetes", "aws", "azure", "gcp",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "machine learning", "deep learning", "nlp", "generative ai", "rag",
    "langchain", "langgraph", "rest api", "rest", "linux", "power bi",
]

def extract_resume_text(file_path: str) -> str:
    path = Path(file_path)
    extension = path.suffix.lower()

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Resume file not found")

    if extension == ".pdf":
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(path).pages
        )
    elif extension == ".docx":
        document = Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(parts)
    else:
        raise HTTPException(
            status_code=400,
            detail="Resume analysis supports only PDF and DOCX files",
        )

    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from this resume",
        )
    return text


def _fallback_analysis(text: str) -> dict:
    lower = text.lower()
    skills = [
        skill for skill in SKILL_CATALOG
        if re.search(r"(?<![a-z0-9+#.])" + re.escape(skill) + r"(?![a-z0-9+#.])", lower)
    ]

    role_candidates = [
        "Python Developer", "Backend Developer", "Frontend Developer",
        "Full Stack Developer", "Software Engineer", "AI Engineer",
        "Machine Learning Engineer", "Data Analyst", "Data Scientist",
    ]
    recommended_roles = []
    for role in role_candidates:
        if all(re.search(r"\b" + re.escape(token) + r"\b", lower) for token in role.lower().split()):
            recommended_roles.append(role)

    certification_lines = []
    for line in text.splitlines():
        if re.search(r"certif|nptel|coursera|edx|ibm|salesforce", line, re.I):
            certification_lines.append(line.strip())

    education_lines = []
    for line in text.splitlines():
        if re.search(r"b\.?(tech|e)|bachelor|master|m\.?(tech|sc)|degree|university|college", line, re.I):
            education_lines.append(line.strip())

    return {
        "summary": "Resume analyzed using the local fallback parser.",
        "skills": skills,
        "technologies": skills,
        "experience": [],
        "education": [{"degree": line, "institution": "", "year": ""} for line in education_lines[:10]],
        "projects": [],
        "certifications": certification_lines[:10],
        "recommended_roles": recommended_roles or ["Software Engineer"],
        "provider": "local-fallback",
    }


def _gemini_failure_message(error: APIError | httpx.HTTPError | json.JSONDecodeError) -> str:
    if isinstance(error, APIError):
        if error.code in {401, 403}:
            reason = "Gemini rejected the API key or the key lacks permission."
        elif error.code == 404:
            reason = f"The Gemini model '{settings.gemini_model}' was not found or is unavailable."
        elif error.code == 429:
            reason = "Gemini rate limit or quota was reached."
        elif error.code is not None and error.code >= 500:
            reason = "The Gemini service is temporarily unavailable."
        else:
            reason = f"Gemini returned HTTP {error.code}."
    elif isinstance(error, httpx.HTTPError):
        reason = "The app could not reach Gemini due to a network or timeout error."
    else:
        reason = "Gemini returned invalid analysis JSON."

    return f"{reason} Local resume analysis was used instead."


def analyze_resume(text: str) -> dict:
    if not settings.gemini_api_key:
        return _fallback_analysis(text)

    prompt = f"""
Analyze the following resume and return ONLY valid JSON. Do not use markdown
code fences or additional text.

Use exactly this schema:
{{
  "summary": "short professional summary",
  "skills": ["skill"],
  "technologies": ["technology"],
  "experience": [
    {{"role": "job title", "company": "company", "duration": "duration", "highlights": ["achievement"]}}
  ],
  "education": [
    {{"degree": "degree", "institution": "institution", "year": "year"}}
  ],
  "projects": [
    {{"name": "project name", "description": "short description", "technologies": ["technology"]}}
  ],
  "certifications": ["certification"],
  "recommended_roles": ["job role"]
}}

Resume:
{text[:30000]}
"""

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        if not isinstance(response.text, str) or not response.text.strip():
            fallback = _fallback_analysis(text)
            fallback["warning"] = "Gemini returned an empty response. Local resume analysis was used instead."
            return fallback
        result = json.loads(response.text)
    except (APIError, httpx.HTTPError, json.JSONDecodeError) as error:
        fallback = _fallback_analysis(text)
        fallback["warning"] = _gemini_failure_message(error)
        return fallback

    if not isinstance(result, dict):
        fallback = _fallback_analysis(text)
        fallback["warning"] = "Gemini returned an invalid analysis response. Local resume analysis was used instead."
        return fallback

    result["provider"] = "gemini"
    return result


def analyze_resume_file(file_path: str) -> tuple[str, dict]:
    text = extract_resume_text(file_path)
    return text, analyze_resume(text)
