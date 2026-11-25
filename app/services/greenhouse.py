"""Greenhouse Job Board API submission adapter."""

import base64
import json
import mimetypes
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass
class GreenhouseSubmissionResult:
    submitted: bool
    message: str
    attempted: bool = False


def _request_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "AI-Job-Application-Agent/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _field_value(name: str, label: str, applicant: dict[str, str | None]) -> str | None:
    normalized_name = name.lower().replace("_", " ")
    if re.search(r"\b(latitude|longitude|country|country short name)\b", normalized_name):
        return None
    key = f"{name} {label}".lower().replace("_", " ")
    if re.search(r"\b(first|given)\s*name\b", key):
        return applicant.get("first_name")
    if re.search(r"\b(last|family)\s*name\b|\bsurname\b", key):
        return applicant.get("last_name")
    if re.search(r"\bemail\b", key):
        return applicant.get("email")
    if re.search(r"\b(phone|mobile|telephone)\b", key):
        return applicant.get("phone")
    if re.search(r"\blocation\b", key):
        location = applicant.get("location")
        if location and location.strip().lower() not in {"remote", "hybrid", "anywhere"}:
            return location
    return None


def _multipart(fields: list[tuple[str, str]], resume_path: Path) -> tuple[bytes, str]:
    boundary = f"----AgentForm{secrets.token_hex(16)}"
    body = bytearray()

    def add_part(content_disposition: str, content_type: str | None, content: bytes) -> None:
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(f"Content-Disposition: form-data; {content_disposition}\r\n".encode("utf-8"))
        if content_type:
            body.extend(f"Content-Type: {content_type}\r\n".encode("ascii"))
        body.extend(b"\r\n")
        body.extend(content)
        body.extend(b"\r\n")

    for name, value in fields:
        safe_name = name.replace('"', "")
        add_part(f'name="{safe_name}"', None, value.encode("utf-8"))

    filename = resume_path.name.replace('"', "")
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    add_part(
        f'name="resume"; filename="{filename}"',
        content_type,
        resume_path.read_bytes(),
    )
    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    return bytes(body), boundary


def submit_application(
    board_token: str | None,
    api_key: str | None,
    job_id: str,
    resume_path: str,
    applicant: dict[str, str | None],
) -> GreenhouseSubmissionResult:
    if not board_token or not api_key:
        return GreenhouseSubmissionResult(
            False,
            "Greenhouse submission is not configured. Set GREENHOUSE_BOARD_TOKEN and GREENHOUSE_API_KEY in the backend .env file.",
        )

    resume = Path(resume_path)
    if not resume.is_file():
        return GreenhouseSubmissionResult(
            False,
            "The selected resume file is unavailable. Re-upload the resume before applying.",
        )

    encoded_board = quote(board_token.strip(), safe="")
    encoded_job = quote(job_id, safe="")
    detail_url = (
        f"https://boards-api.greenhouse.io/v1/boards/{encoded_board}/jobs/"
        f"{encoded_job}?questions=true"
    )
    endpoint = (
        f"https://boards-api.greenhouse.io/v1/boards/{encoded_board}/jobs/{encoded_job}"
    )

    try:
        job = _request_json(detail_url)
    except HTTPError as error:
        if error.code in {401, 403}:
            return GreenhouseSubmissionResult(
                False,
                "Greenhouse rejected the board API key or it lacks permission for this board.",
            )
        if error.code == 404:
            return GreenhouseSubmissionResult(
                False,
                "The Greenhouse job was not found on the configured board.",
            )
        return GreenhouseSubmissionResult(
            False, f"Greenhouse could not load this job's application questions (HTTP {error.code})."
        )
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        return GreenhouseSubmissionResult(False, f"Could not load Greenhouse application questions: {error}")

    full_name = (applicant.get("full_name") or "").strip().split()
    applicant = {
        **applicant,
        "first_name": full_name[0] if full_name else None,
        "last_name": " ".join(full_name[1:]) if len(full_name) > 1 else None,
    }
    fields: list[tuple[str, str]] = []
    missing: list[str] = []
    has_resume_question = False

    for question_group in ("questions", "location_questions", "compliance"):
        for question in job.get(question_group, []):
            label = str(question.get("label") or question.get("name") or "")
            required = bool(question.get("required"))
            question_fields = question.get("fields") or []
            if not question_fields:
                if required:
                    missing.append(label or "required application question")
                continue

            question_filled = False
            for field in question_fields:
                name = str(field.get("name") or "")
                field_type = str(field.get("type") or "")
                if field_type == "input_file" and re.search(r"\b(resume|cv)\b", f"{name} {label}", re.I):
                    has_resume_question = True
                    question_filled = True
                    continue
                value = _field_value(name, label, applicant)
                if value and field_type in {"input_text", "input_hidden", "textarea"}:
                    fields.append((name, value))
                    question_filled = True
                    continue
                if required and field_type in {"input_text", "input_hidden", "textarea"}:
                    missing.append(label or name or "required application question")
            if required and not question_filled and not any(
                item.startswith(label) for item in missing
            ):
                missing.append(label or "required application question")

    if not has_resume_question:
        missing.append("Resume upload field")
    if missing:
        labels = ", ".join(dict.fromkeys(missing[:6]))
        return GreenhouseSubmissionResult(
            False,
            f"Greenhouse requires information this profile cannot safely supply ({labels}). The form was not submitted.",
        )

    payload, boundary = _multipart(fields, resume)
    encoded_key = base64.b64encode(api_key.encode("utf-8")).decode("ascii")
    request = Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {encoded_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AI-Job-Application-Agent/1.0",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
            if 200 <= response.status < 300:
                return GreenhouseSubmissionResult(
                    True, "Greenhouse accepted the application submission.", attempted=True
                )
            return GreenhouseSubmissionResult(
                False,
                f"Greenhouse did not accept the application (HTTP {response.status}).",
                attempted=True,
            )
    except HTTPError as error:
        detail = error.read(1024).decode("utf-8", errors="replace")
        if error.code in {401, 403}:
            return GreenhouseSubmissionResult(
                False, "Greenhouse rejected the board API key or it lacks permission for this board."
            )
        return GreenhouseSubmissionResult(
            False,
            f"Greenhouse rejected the application (HTTP {error.code}): {detail}",
            attempted=True,
        )
    except (URLError, TimeoutError, OSError) as error:
        return GreenhouseSubmissionResult(
        False,
        f"Greenhouse application submission failed: {error}",
        attempted=True,
        )
