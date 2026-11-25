"""Conservative browser-based submissions for public job application forms."""

import ipaddress
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class ApplicationLaunchResult:
    submitted: bool
    application_url: str
    message: str
    attempted: bool = False


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise ValueError("Automatic applications require a public HTTPS address.")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise ValueError("Private and local application URLs are not supported.")

    try:
        addresses = {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            }
        except OSError as error:
            raise ValueError("The application website could not be resolved.") from error

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private and non-public application URLs are not supported.")


def _field_value(description: dict, applicant: dict[str, str | None]) -> str | None:
    text = " ".join(
        str(description.get(key) or "")
        for key in ("name", "placeholder", "label", "aria")
    ).lower()
    autocomplete = str(description.get("autocomplete") or "").lower()
    input_type = str(description.get("type") or "").lower()

    if input_type == "email" or "email" in autocomplete or re.search(r"\be-?mail\b", text):
        return applicant.get("email")
    if input_type == "tel" or "tel" in autocomplete or re.search(r"\b(phone|mobile|telephone)\b", text):
        return applicant.get("phone")
    full_name = applicant.get("full_name")
    first_name, _, last_name = (full_name or "").partition(" ")
    if re.search(r"\b(first|given)\s*name\b", text) or autocomplete == "given-name":
        return first_name or None
    if re.search(r"\b(last|family)\s*name\b|\bsurname\b", text) or autocomplete == "family-name":
        return last_name or None
    if not re.search(r"\b(company|organization|employer)\b", text) and (
        re.search(r"\b(full|applicant|your)\s*name\b|\bname\b", text)
        or autocomplete == "name"
    ):
        return full_name
    if "address-level" in autocomplete or re.search(r"\b(city|location|address)\b", text):
        return applicant.get("location")
    return None


class ApplicationAgent:
    def submit_application(
        self,
        application_url: str,
        resume_path: str,
        applicant: dict[str, str | None],
    ) -> ApplicationLaunchResult:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ApplicationLaunchResult(
                submitted=False,
                application_url=application_url,
                message="Browser auto-apply is unavailable. Install the Playwright dependency and its Chromium browser.",
            )

        resume = Path(resume_path)
        if not resume.is_file():
            return ApplicationLaunchResult(
                submitted=False,
                application_url=application_url,
                message="The selected resume file is unavailable. Re-upload the resume before applying.",
            )

        try:
            _validate_public_url(application_url)
        except ValueError as error:
            return ApplicationLaunchResult(False, application_url, str(error))

        submission_attempted = False
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    checked_hosts: dict[str, bool] = {}

                    def guard_request(route):
                        request_url = route.request.url
                        parsed = urlparse(request_url)
                        if parsed.scheme != "https":
                            route.abort()
                            return
                        hostname = parsed.hostname or ""
                        if hostname not in checked_hosts:
                            try:
                                _validate_public_url(request_url)
                                checked_hosts[hostname] = True
                            except ValueError:
                                checked_hosts[hostname] = False
                        if checked_hosts[hostname]:
                            route.continue_()
                        else:
                            route.abort()

                    page.route("**/*", guard_request)
                    page.goto(application_url, wait_until="domcontentloaded", timeout=20000)

                    if page.locator('input[type="password"]').count():
                        return ApplicationLaunchResult(
                            False, application_url,
                            "This application requires a sign-in. No credentials were entered; open the job page to continue.",
                        )

                    page_text = page.locator("body").inner_text(timeout=5000)
                    if re.search(r"captcha|verify you are human|security challenge|access denied", page_text, re.I) \
                            or page.locator('iframe[src*="captcha"], iframe[title*="challenge" i]').count():
                        return ApplicationLaunchResult(
                            False, application_url,
                            "The job site requires a CAPTCHA or security check. It was not bypassed; open the job page to continue.",
                        )

                    application_form = None
                    forms = page.locator("form")
                    for index in range(forms.count()):
                        form = forms.nth(index)
                        form_metadata = form.evaluate(
                            """element => [
                                element.action,
                                element.id,
                                element.className,
                                element.getAttribute("aria-label"),
                                element.innerText
                            ].join(" ")"""
                        )
                        form_fields = form.locator("input, textarea, select")
                        form_field_types = form_fields.evaluate_all(
                            "elements => elements.map(element => element.type)"
                        )
                        has_applicant_field = any(
                            field_type in {"email", "file"}
                            for field_type in form_field_types
                        )
                        looks_like_application = bool(
                            re.search(r"apply|application|resume|\bcv\b|candidate", form_metadata, re.I)
                        )
                        has_submit = (
                            form.locator('input[type="submit"], button[type="submit"]').count()
                            or form.get_by_role("button").count()
                        )
                        if has_applicant_field and looks_like_application and has_submit:
                            application_form = form
                            break

                    if application_form is None:
                        return ApplicationLaunchResult(
                            False, application_url,
                            "No supported public application form was found. Open the job page to continue manually.",
                        )

                    fields = application_form.locator("input, textarea, select")
                    field_descriptions = fields.evaluate_all(
                        """elements => elements.map(element => {
                            const labels = Array.from(element.labels || [])
                                .map(label => label.innerText || "")
                                .join(" ");
                            return {
                                name: element.name,
                                placeholder: element.placeholder,
                                label: labels,
                                aria: element.getAttribute("aria-label"),
                                autocomplete: element.autocomplete,
                                type: element.type,
                                required: element.required,
                                value: element.value
                            };
                        })"""
                    )

                    for index, description in enumerate(field_descriptions):
                        locator = fields.nth(index)
                        input_type = str(description.get("type") or "").lower()
                        if input_type == "file":
                            file_text = " ".join(
                                str(description.get(key) or "")
                                for key in ("name", "placeholder", "label", "aria")
                            ).lower()
                            file_inputs = sum(
                                str(item.get("type") or "").lower() == "file"
                                for item in field_descriptions
                            )
                            if re.search(r"\b(resume|cv)\b", file_text) or file_inputs == 1:
                                locator.set_input_files(str(resume.resolve()))
                            continue

                        value = _field_value(description, applicant)
                        if value and input_type in {"email", "tel", "text", "search"}:
                            locator.fill(value)

                    missing_required = fields.evaluate_all(
                        """elements => elements.filter(element =>
                            element.required &&
                            element.type !== "submit" &&
                            element.type !== "button" &&
                            element.type !== "hidden" &&
                            (["checkbox", "radio"].includes(element.type)
                                ? !element.checked
                                : !element.value)
                        ).map(element => element.labels?.[0]?.innerText || element.name || element.type)"""
                    )
                    if missing_required:
                        fields_to_fill = ", ".join(str(item) for item in missing_required[:5])
                        return ApplicationLaunchResult(
                            False, application_url,
                            f"Required application details are missing ({fields_to_fill}). The form was not submitted.",
                        )

                    for selector in ('input[type="submit"]', 'button[type="submit"]'):
                        submit = application_form.locator(selector).first
                        if submit.count():
                            submission_attempted = True
                            submit.click(timeout=5000)
                            break
                    else:
                        buttons = application_form.get_by_role("button")
                        submit_index = None
                        for index in range(buttons.count()):
                            if re.fullmatch(r"(submit|submit application|send application|apply|apply now)", buttons.nth(index).inner_text().strip(), re.I):
                                submit_index = index
                                break
                        if submit_index is None:
                            return ApplicationLaunchResult(
                                False, application_url,
                                "No supported application submit button was found. Open the job page to apply manually.",
                            )
                        submission_attempted = True
                        buttons.nth(submit_index).click(timeout=5000)

                    page.wait_for_timeout(1500)
                    confirmation = page.locator("body").inner_text(timeout=5000)
                    confirmation_pattern = re.compile(
                        r"thank you|application (?:has been|was|is) received|"
                        r"successfully submitted|submitted successfully|"
                        r"we have received|received your application",
                        re.I,
                    )
                    if (
                        confirmation_pattern.search(confirmation)
                        and not confirmation_pattern.search(page_text)
                    ):
                        return ApplicationLaunchResult(
                            True, application_url,
                            "The job site confirmed that your application was submitted.",
                            attempted=True,
                        )

                    return ApplicationLaunchResult(
                        False, application_url,
                        "The form was submitted, but the job site did not confirm receipt. Check the job page before trying again.",
                        attempted=True,
                    )
                finally:
                    browser.close()
        except (PlaywrightTimeoutError, PlaywrightError, OSError, ValueError) as error:
            return ApplicationLaunchResult(
                False,
                application_url,
                f"Automatic application could not be completed: {error}",
                attempted=submission_attempted,
            )
