// ============================================================
// Shared helpers
// ============================================================

function formatApiError(result, fallbackMessage) {
    const detail = result && result.detail;

    if (Array.isArray(detail)) {
        return detail.map(function (error) {
            if (error && typeof error === "object") {
                const location = Array.isArray(error.loc)
                    ? error.loc.join(".")
                    : "";
                const message = error.msg || error.message || JSON.stringify(error);
                return location ? `${location}: ${message}` : message;
            }
            return String(error);
        }).join(", ");
    }

    if (detail && typeof detail === "object") {
        return detail.msg || detail.message || JSON.stringify(detail);
    }

    return detail ? String(detail) : fallbackMessage;
}

function getToken() {
    return localStorage.getItem("access_token");
}

function getAuthHeaders() {
    const token = getToken();
    const currentPath = window.location.pathname;

    document.querySelectorAll("#publicNav a, #userNav a").forEach(function (link) {
        const linkPath = new URL(link.href, window.location.origin).pathname;
        if (linkPath === currentPath || (currentPath === "/" && linkPath === "/")) {
            link.classList.add("nav-current");
            link.setAttribute("aria-current", "page");
        }
    });
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function clearAuthentication() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
}

function redirectToLoginIfUnauthorized(response) {
    if (response.status === 401) {
        clearAuthentication();
        window.location.href = "/login";
        return true;
    }
    return false;
}

function requireAuthentication() {
    if (!getToken()) {
        window.location.href = "/login";
        return false;
    }
    return true;
}

async function readJson(response) {
    try {
        return await response.json();
    } catch (error) {
        return {};
    }
}


// ============================================================
// Navigation
// ============================================================

const publicNav = document.getElementById("publicNav");
const userNav = document.getElementById("userNav");
const logoutButton = document.getElementById("logoutButton");
const token = getToken();

if (token) {
    if (publicNav) publicNav.style.display = "none";
    if (userNav) userNav.style.display = "flex";
} else {
    if (publicNav) publicNav.style.display = "flex";
    if (userNav) userNav.style.display = "none";
}

if (logoutButton) {
    logoutButton.addEventListener("click", function (event) {
        event.preventDefault();
        clearAuthentication();
        window.location.href = "/";
    });
}


// ============================================================
// Login
// ============================================================

const loginForm = document.getElementById("loginForm");

if (loginForm) {
    loginForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const message = document.getElementById("loginMessage");
        const formData = new FormData();
        formData.append("username", document.getElementById("username").value.trim());
        formData.append("password", document.getElementById("password").value);

        try {
            const response = await fetch("/auth/login", {
                method: "POST",
                body: formData
            });
            const result = await readJson(response);

            if (!response.ok) {
                message.textContent = formatApiError(result, "Login failed.");
                message.style.color = "red";
                return;
            }

            localStorage.setItem("access_token", result.access_token);
            localStorage.setItem("user", JSON.stringify(result.user));
            message.textContent = "Login successful. Redirecting...";
            message.style.color = "green";

            window.location.href = "/dashboard";
        } catch (error) {
            console.error("Login error:", error);
            message.textContent = "Unable to connect to the server.";
            message.style.color = "red";
        }
    });
}


// ============================================================
// Registration
// ============================================================

const registerForm = document.getElementById("registerForm");

if (registerForm) {
    registerForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const message = document.getElementById("registerMessage");
        const value = function (id) {
            const element = document.getElementById(id);
            return element ? element.value.trim() : "";
        };

        const data = {
            username: value("username"),
            email: value("email"),
            password: document.getElementById("password").value,
            full_name: value("full_name") || null,
            phone: value("phone") || null,
            location: value("location") || null,
            experience: value("experience") || null,
            education: value("education") || null,
            preferred_roles: value("preferred_roles") || null,
            preferred_locations: value("preferred_locations") || null
        };

        try {
            const response = await fetch("/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });
            const result = await readJson(response);

            if (!response.ok) {
                message.textContent = formatApiError(result, "Registration failed.");
                message.style.color = "red";
                return;
            }

            message.textContent = "Registration successful. Redirecting to login...";
            message.style.color = "green";
            registerForm.reset();
            setTimeout(function () {
                window.location.href = "/login";
            }, 700);
        } catch (error) {
            console.error("Registration error:", error);
            message.textContent = "Unable to connect to the server.";
            message.style.color = "red";
        }
    });
}

// ============================================================
// Contact
// ============================================================

const contactForm = document.getElementById("contactForm");

if (contactForm) {
    contactForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const message = document.getElementById("contactFormMessage");
        const submitButton = document.getElementById("contactSubmit");
        const data = {
            name: document.getElementById("contactName").value.trim(),
            email: document.getElementById("contactEmail").value.trim(),
            subject: document.getElementById("contactSubject").value.trim(),
            message: document.getElementById("contactMessageText").value.trim()
        };

        submitButton.disabled = true;
        submitButton.textContent = "Sending...";
        message.textContent = "";

        try {
            const response = await fetch("/api/contact", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });
            const result = await readJson(response);

            if (!response.ok) {
                message.textContent = formatApiError(result, "Unable to send your message.");
                message.className = "contact-form-message is-error";
                return;
            }

            contactForm.reset();
            message.textContent = result.message || "Your message has been sent.";
            message.className = "contact-form-message is-success";
        } catch (error) {
            console.error("Contact form error:", error);
            message.textContent = "Unable to connect to the server. Your message was not sent.";
            message.className = "contact-form-message is-error";
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Send message";
        }
    });
}


// ============================================================
// Profile
// ============================================================

const profileUsername = document.getElementById("profileUsername");

async function loadProfile() {
    if (!profileUsername || !requireAuthentication()) return;

    try {
        const response = await fetch("/profiles/me", {
            headers: getAuthHeaders()
        });
        const result = await readJson(response);

        if (redirectToLoginIfUnauthorized(response)) return;

        if (!response.ok) {
            console.error(formatApiError(result, "Unable to load profile."));
            return;
        }

        const fields = {
            profileFullName: result.full_name,
            profileUsername: result.username,
            profileEmail: result.email,
            profilePhone: result.phone,
            profileLocation: result.location,
            profileExperience: result.experience,
            profileEducation: result.education,
            profileRoles: result.preferred_roles,
            profileLocations: result.preferred_locations
        };

        Object.keys(fields).forEach(function (id) {
            const element = document.getElementById(id);
            if (element) element.textContent = fields[id] || "Not provided";
        });
    } catch (error) {
        console.error("Profile loading error:", error);
    }
}

loadProfile();


// ============================================================
// Update profile
// ============================================================

const updateProfileForm = document.getElementById("updateProfileForm");

async function loadProfileForUpdate() {
    if (!updateProfileForm || !requireAuthentication()) return;

    try {
        const response = await fetch("/profiles/me", {
            headers: getAuthHeaders()
        });
        const result = await readJson(response);

        if (redirectToLoginIfUnauthorized(response)) return;
        if (!response.ok) return;

        ["full_name", "phone", "location", "experience", "education", "preferred_roles", "preferred_locations"].forEach(function (id) {
            const element = document.getElementById(id);
            if (element) element.value = result[id] || "";
        });
    } catch (error) {
        console.error("Profile update form loading error:", error);
    }
}

loadProfileForUpdate();

if (updateProfileForm) {
    updateProfileForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (!requireAuthentication()) return;

        const message = document.getElementById("updateProfileMessage");
        const data = {};

        ["full_name", "phone", "location", "experience", "education", "preferred_roles", "preferred_locations"].forEach(function (id) {
            const element = document.getElementById(id);
            data[id] = element && element.value.trim() ? element.value.trim() : null;
        });

        try {
            const response = await fetch("/profiles/me", {
                method: "PUT",
                headers: {
                    ...getAuthHeaders(),
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(data)
            });
            const result = await readJson(response);

            if (redirectToLoginIfUnauthorized(response)) return;

            if (!response.ok) {
                message.textContent = formatApiError(result, "Failed to update profile.");
                message.style.color = "red";
                return;
            }

            message.textContent = "Profile updated successfully!";
            message.style.color = "green";
            window.location.href = "/profiles";
            
        } catch (error) {
            console.error("Profile update error:", error);
            message.textContent = "Unable to connect to the server.";
            message.style.color = "red";
        }
    });
}


// ============================================================
// Resume management
// ============================================================

const resumeList = document.getElementById("resumeList");
const resumeUploadForm = document.getElementById("resumeUploadForm");

async function renderResumes() {
    if (!resumeList || !requireAuthentication()) return;

    resumeList.innerHTML = '<p class="resume-loading-card">Loading your resume library...</p>';

    try {
        const response = await fetch("/api/resumes", {
            headers: getAuthHeaders()
        });
        const result = await readJson(response);

        if (redirectToLoginIfUnauthorized(response)) return;

        if (!response.ok) {
            resumeList.innerHTML = `<p>${formatApiError(result, "Unable to load resumes.")}</p>`;
            return;
        }

        const resumes = result.resumes || [];
        resumeList.innerHTML = "";

        if (!resumes.length) {
            resumeList.innerHTML = '<div class="empty-state"><span class="empty-state-icon">▤</span><h3>Your resume library is ready</h3><p>Upload your first resume to start matching with relevant opportunities.</p></div>';
            return;
        }

        resumes.forEach(function (resume) {
            const card = document.createElement("article");
            card.className = "resume-card";

            const icon = document.createElement("div");
            icon.className = "resume-card-icon";
            icon.textContent = "▤";

            const content = document.createElement("div");
            content.className = "resume-card-content";

            const title = document.createElement("h3");
            title.textContent = resume.name || "Unnamed resume";

            const path = document.createElement("p");
            path.textContent = resume.analysis
                ? "PDF or DOCX · Analyzed and ready to match"
                : "PDF or DOCX · Analysis pending";

            content.appendChild(title);
            content.appendChild(path);

            if (resume.analysis) {
                const summary = document.createElement("p");
                summary.className = "resume-analysis-summary";
                const skills = resume.analysis.skills || [];
                summary.textContent = skills.length
                    ? `Skills: ${skills.slice(0, 8).join(", ")}`
                    : "AI analysis completed.";
                content.appendChild(summary);

                if (resume.analysis.warning) {
                    const warning = document.createElement("p");
                    warning.className = "resume-analysis-warning";
                    warning.textContent = resume.analysis.warning;
                    content.appendChild(warning);
                }
            }

            const actions = document.createElement("div");
            actions.className = "resume-card-actions";

            const deleteButton = document.createElement("button");
            deleteButton.className = "btn delete-resume-btn";
            deleteButton.type = "button";
            deleteButton.dataset.id = resume.id;
            deleteButton.textContent = "Delete";

            actions.appendChild(deleteButton);

            card.appendChild(icon);
            card.appendChild(content);
            card.appendChild(actions);
            resumeList.appendChild(card);
        });

        attachResumeButtons();
    } catch (error) {
        console.error("Resume loading error:", error);
        resumeList.innerHTML = "<p>Unable to connect to the server.</p>";
    }
}

if (resumeList) renderResumes();

if (resumeUploadForm) {
    resumeUploadForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (!requireAuthentication()) return;

        const message = document.getElementById("resumeUploadMessage");
        const file = document.getElementById("resumeFile").files[0];
        const name = document.getElementById("resumeName").value.trim();

        if (!file) {
            message.textContent = "Please select a PDF or DOCX file.";
            message.style.color = "red";
            return;
        }

        const extension = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
        if (![".pdf", ".docx"].includes(extension)) {
            message.textContent = "Only PDF and DOCX files are allowed.";
            message.style.color = "red";
            return;
        }

        const formData = new FormData();
        formData.append("name", name);
        formData.append("file", file);

        try {
            message.textContent = "Uploading...";
            message.style.color = "black";

            const response = await fetch("/api/resumes/upload", {
                method: "POST",
                headers: getAuthHeaders(),
                body: formData
            });
            const result = await readJson(response);

            if (redirectToLoginIfUnauthorized(response)) return;

            if (!response.ok) {
                message.textContent = formatApiError(result, "Resume upload failed.");
                message.style.color = "red";
                return;
            }

            message.textContent = result.message || "Resume uploaded and analyzed successfully.";
            message.style.color = result.resume.analysis.warning ? "#a65346" : "green";
            resumeUploadForm.reset();
            await renderResumes();
        } catch (error) {
            console.error("Resume upload error:", error);
            message.textContent = "Unable to connect to the server.";
            message.style.color = "red";
        }
    });
}

function attachResumeButtons() {
    document.querySelectorAll(".delete-resume-btn").forEach(function (button) {
        button.addEventListener("click", async function () {
            const id = button.dataset.id;
            if (!window.confirm("Delete this resume permanently?")) return;

            button.disabled = true;
            button.textContent = "Deleting...";

            try {
                const response = await fetch(`/api/resumes/${id}`, {
                    method: "DELETE",
                    headers: getAuthHeaders()
                });
                const result = await readJson(response);

                if (redirectToLoginIfUnauthorized(response)) return;
                if (!response.ok) {
                    alert(formatApiError(result, "Resume deletion failed."));
                    button.disabled = false;
                    button.textContent = "Delete";
                    return;
                }

                await renderResumes();
            } catch (error) {
                console.error("Resume deletion error:", error);
                alert("Unable to connect to the server.");
                button.disabled = false;
                button.textContent = "Delete";
            }
        });
    });
}


// ============================================================
// AI Job Agent
// ============================================================

const refreshAiJobsButton = document.getElementById("refreshAiJobs");
const agentResults = document.getElementById("agentResults");
const agentMessage = document.getElementById("agentMessage");

async function loadAiJobs() {
    if (!agentResults || !agentMessage || !refreshAiJobsButton) return;
    if (!requireAuthentication()) return;

    refreshAiJobsButton.disabled = true;
    refreshAiJobsButton.textContent = "Running...";
    agentMessage.textContent = "Discovering jobs and matching them to your resumes...";
    agentMessage.style.color = "black";
    agentResults.innerHTML = "";

    try {
        const response = await fetch("/api/agent/run", {
            method: "POST",
            headers: getAuthHeaders()
        });
        const result = await readJson(response);

        if (redirectToLoginIfUnauthorized(response)) return;

        if (!response.ok) {
            agentMessage.textContent = formatApiError(result, "AI agent failed.");
            agentMessage.style.color = "red";
            return;
        }

        const recommendations = result.recommendations || [];
        agentMessage.textContent = `${recommendations.length} matching jobs found. Open a listing or try AutoApply.`;
        agentMessage.style.color = "green";

        if (result.source_errors && result.source_errors.length) {
            const warning = document.createElement("p");
            warning.className = "info-note";
            warning.textContent = `Some sources were unavailable: ${result.source_errors.join(" | ")}`;
            agentResults.appendChild(warning);
        }

        if (result.analysis_warnings && result.analysis_warnings.length) {
            const warning = document.createElement("p");
            warning.className = "info-note";
            warning.textContent = result.analysis_warnings.join(" | ");
            agentResults.appendChild(warning);
        }

        if (!recommendations.length) {
            const empty = document.createElement("p");
            empty.textContent = "No matching jobs were found. Update your profile or preferred roles to broaden the search.";
            agentResults.appendChild(empty);
            return;
        }

        recommendations.forEach(function (item) {
            const card = document.createElement("article");
            card.className = "agent-job-card";

            const title = document.createElement("h3");
            title.textContent = item.job.title;

            const company = document.createElement("p");
            company.className = "agent-company";
            company.textContent = `${item.job.company} · ${item.job.location || "Remote"}`;

            const score = document.createElement("p");
            score.className = "match-score";
            score.innerHTML = "Match score: ";
            const scoreStrong = document.createElement("strong");
            scoreStrong.textContent = `${item.match_score}%`;
            score.appendChild(scoreStrong);

            const resume = document.createElement("p");
            resume.textContent = `Selected resume: ${item.selected_resume.name}`;

            const terms = document.createElement("p");
            terms.textContent = item.matched_terms.length
                ? `Matched terms: ${item.matched_terms.join(", ")}`
                : "Matched terms: profile and resume criteria";

            const actions = document.createElement("div");
            actions.className = "agent-job-actions";

            const openApplication = document.createElement("a");
            openApplication.className = "btn secondary";
            openApplication.href = item.job.application_url;
            openApplication.target = "_blank";
            openApplication.rel = "noopener noreferrer";
            openApplication.textContent = "Open Application";

            const autoApplyButton = document.createElement("button");
            autoApplyButton.className = "btn";
            autoApplyButton.type = "button";
            autoApplyButton.textContent = "AutoApply";
            autoApplyButton.addEventListener("click", async function () {
                autoApplyButton.disabled = true;
                autoApplyButton.textContent = "Applying...";
                try {
                    const response = await fetch("/api/agent/apply", {
                        method: "POST",
                        headers: {
                            ...getAuthHeaders(),
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            job: item.job,
                            resume_id: item.selected_resume.id,
                            match_score: item.match_score,
                            recommendation_token: item.recommendation_token
                        })
                    });
                    const result = await readJson(response);

                    if (redirectToLoginIfUnauthorized(response)) {
                        return;
                    }
                    if (!response.ok) {
                        agentMessage.textContent = formatApiError(result, "Unable to save or submit this application.");
                        return;
                    }

                    const applicationNotice = document.createElement("p");
                    applicationNotice.className = result.submitted
                        ? "application-status"
                        : "application-saved-notice";
                    applicationNotice.textContent = result.submitted
                        ? "Applied — submission confirmed."
                        : "Saved to your account and listed in Applications. Submission is not confirmed.";
                    const existingNotice = card.querySelector(
                        ".application-status, .application-saved-notice"
                    );
                    if (existingNotice) existingNotice.remove();
                    card.insertBefore(applicationNotice, actions);
                    agentMessage.textContent = result.message;

                    if (result.submitted) {
                        autoApplyButton.textContent = "Applied";
                        autoApplyButton.disabled = true;
                    } else if (result.attempted) {
                        autoApplyButton.textContent = "Submission Unconfirmed";
                        autoApplyButton.disabled = true;
                    } else {
                        autoApplyButton.textContent = "Retry AutoApply";
                    }
                } catch (error) {
                    console.error("Application launch error:", error);
                    agentMessage.textContent = "Unable to connect to the server. The application may not have been saved; please retry.";
                } finally {
                    if (autoApplyButton.textContent === "Applying...") {
                        autoApplyButton.textContent = "AutoApply";
                    }
                    autoApplyButton.disabled = [
                        "Applied",
                        "Submission Unconfirmed"
                    ].includes(autoApplyButton.textContent);
                }
            });

            card.appendChild(title);
            card.appendChild(company);
            card.appendChild(score);
            card.appendChild(resume);
            card.appendChild(terms);
            actions.appendChild(openApplication);
            actions.appendChild(autoApplyButton);
            card.appendChild(actions);
            agentResults.appendChild(card);
        });
    } catch (error) {
        console.error("AI agent error:", error);
        agentMessage.textContent = "Unable to connect to the server.";
        agentMessage.style.color = "red";
    } finally {
        refreshAiJobsButton.disabled = false;
        refreshAiJobsButton.textContent = "Run Agent";
    }
}

if (refreshAiJobsButton) {
    refreshAiJobsButton.addEventListener("click", loadAiJobs);
    loadAiJobs();
}


// ============================================================
// Applications
// ============================================================

const applicationsList = document.getElementById("applicationsList");
const applicationsMessage = document.getElementById("applicationsMessage");

async function loadApplications() {
    if (!applicationsList || !applicationsMessage || !requireAuthentication()) return;

    try {
        const response = await fetch("/api/applications", {
            headers: getAuthHeaders()
        });
        const result = await readJson(response);

        if (redirectToLoginIfUnauthorized(response)) return;

        if (!response.ok) {
            applicationsMessage.textContent = formatApiError(result, "Unable to load applications.");
            return;
        }

        const applications = result.applications || [];
        applicationsList.innerHTML = "";
        const confirmedCount = applications.filter(function (item) {
            return item.status === "applied";
        }).length;
        applicationsMessage.textContent = applications.length
            ? `${applications.length} saved application(s), ${confirmedCount} confirmed.`
            : "";

        if (!applications.length) {
            applicationsList.innerHTML = '<div class="empty-state"><span class="empty-state-icon">↗</span><h3>No saved applications yet</h3><p>Jobs you choose with AutoApply will appear here.</p><a class="btn" href="/ai-jobs">Discover jobs <span aria-hidden="true">↗</span></a></div>';
            return;
        }

        applications.forEach(function (item) {
            const card = document.createElement("article");
            card.className = "agent-job-card";

            const title = document.createElement("h3");
            title.textContent = item.job_title || "Unknown job";

            const company = document.createElement("p");
            company.textContent = `${item.company || "Unknown company"} · ${item.location || "Remote"}`;

            const resume = document.createElement("p");
            resume.textContent = `Resume: ${item.resume_name || "Unknown"}`;

            const score = document.createElement("p");
            score.textContent = `Match score: ${item.match_score == null ? "Not recorded" : `${item.match_score}%`}`;

            const statusBadge = document.createElement("span");
            const confirmed = item.status === "applied";
            statusBadge.className = confirmed
                ? "status-badge status-applied"
                : "status-badge";
            statusBadge.textContent = confirmed ? "Applied" : "Saved — not confirmed";

            card.appendChild(title);
            card.appendChild(company);
            card.appendChild(resume);
            card.appendChild(score);
            card.appendChild(statusBadge);

            if (item.application_url) {
                const link = document.createElement("a");
                link.className = "btn";
                link.href = item.application_url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = "Open Application";
                card.appendChild(link);
            }

            applicationsList.appendChild(card);
        });
    } catch (error) {
        console.error("Application loading error:", error);
        applicationsMessage.textContent = "Unable to connect to the server.";
    }
}

loadApplications();
