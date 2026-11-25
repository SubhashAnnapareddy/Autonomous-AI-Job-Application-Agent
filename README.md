# EasyApply

A FastAPI + PostgreSQL + SQLAlchemy project that demonstrates an agentic job-search workflow:

1. User registration and JWT authentication
2. User profile management
3. Multiple resume upload (PDF/DOCX)
4. Automatic resume text extraction and analysis on upload
5. AI resume analysis with Gemini, with a local fallback when Gemini is not configured or the Gemini request fails
6. Job discovery from supported public job APIs
7. Job matching against analyzed resume skills, preferred roles, location and stated experience
8. Automatic selection of the best resume for each matched job
9. Job recommendations remain temporary until the user clicks Apply
10. Application history and status management for jobs the user chooses to apply to
11. Contact form messages saved for the project team

## Overview and contact

The Overview page explains the setup and job-search workflow, including the difference between a saved application and a destination-confirmed submission. The Contact page accepts questions and feedback and stores each message in the `contact_messages` database table.

## Application submission

The agent discovers jobs without storing them. On a recommendation, **Open Application** visits the employer's listing without saving it; **AutoApply** saves the selected job/application record first, then attempts a supported submission. Remotive and Arbeitnow listings use conservative browser automation; unsupported or unconfirmed forms remain internally `ready`, and the user can open the employer listing separately to complete the application. The Applications page shows both saved applications awaiting confirmation and submissions confirmed by the destination site, with the distinction made clear.

The optional Greenhouse integration discovers jobs from one configured board and submits using Greenhouse's official Job Board API. Greenhouse Job Board API keys are issued by the employer/owner of that board. They are not general job-seeker keys and cannot submit applications to unrelated employers' boards. Configure a board you own or have permission to use. The adapter reads each job's required questions and will not guess answers or submit when required information is missing. It does not bypass CAPTCHA, anti-bot systems, authentication, or platform restrictions.

Greenhouse API documentation: [Job Board API](https://developers.greenhouse.io/job-board.html).

### Browser auto-apply setup

Install the Python dependencies, then install the Playwright Chromium browser:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Apply the latest database migrations after setup or pulling schema changes:

```powershell
alembic upgrade head
```

Add your full name, phone number, and location in your profile. The agent uses these details and your selected resume to fill supported application fields. It does not answer custom application questions or guess missing information.

## Project structure

```text
backend/
├── app/
│   ├── api/
│   │   ├── agent.py
│   │   ├── applications.py
│   │   ├── auth.py
│   │   ├── contact.py
│   │   ├── profiles.py
│   │   └── resumes.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── database/
│   │   ├── base.py
│   │   └── connection.py
│   ├── models/
│   │   ├── application.py
│   │   ├── contact_message.py
│   │   ├── job.py
│   │   ├── profile.py
│   │   ├── resume.py
│   │   └── user.py
│   ├── services/
│   │   ├── application_agent.py
│   │   ├── greenhouse.py
│   │   ├── job_agent.py
│   │   └── resume_intelligence.py
│   ├── schemas/auth.py
│   ├── templates/
│   └── static/
├── migrations/
├── uploads/resumes/
├── .env.example
├── alembic.ini
└── requirements.txt
```

## Setup on Windows

Open PowerShell inside the `backend` folder:

```powershell
python -m venv myenv
.\myenv\Scripts\Activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your PostgreSQL credentials:

```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/ai_job_agent
SECRET_KEY=use-a-long-random-secret
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GREENHOUSE_BOARD_TOKEN=
GREENHOUSE_API_KEY=
```

For Greenhouse, set `GREENHOUSE_BOARD_TOKEN` to the token in the board URL (for example, `boards.greenhouse.io/{board_token}`) and `GREENHOUSE_API_KEY` to a Job Board API key issued by that board's owner. Keep the key in `backend/.env`; never put it in frontend JavaScript, commit it, or send it in chat. A Greenhouse administrator must issue the key; a public job listing or personal candidate account does not provide it. If these settings are empty, the Greenhouse job source is disabled and Remotive/Arbeitnow continue to work.

Then run:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## PostgreSQL

Create the database before running migrations:

```sql
CREATE DATABASE ai_job_agent;
```

The application uses SQLAlchemy for database access and Alembic for schema migrations.

## Gemini

Gemini is optional for local execution. If `GEMINI_API_KEY` is empty, resume analysis uses the built-in local fallback parser so the application remains usable.

Uploaded resumes are automatically analyzed before job matching. If a Gemini key is supplied, the resume intelligence service extracts:

- summary
- skills
- technologies
- experience
- education
- projects
- certifications
- recommended roles

## Agent workflow

```text
User
 ↓
Profile + Multiple Resumes
 ↓
Job Discovery Agent
 ↓
Temporary Recommendations
 ↓
Job Matching Agent
 ↓
Resume Selection Agent
 ↓
User Clicks Apply
 ↓
Job Database + Application Tracking
 ↓
Browser Form Submission + Confirmation
```

## API overview

### Authentication

- `POST /auth/register`
- `POST /auth/login`

### Profile

- `GET /profiles/me`
- `PUT /profiles/me`

### Resumes

- `POST /api/resumes/upload`
- `GET /api/resumes`
- `POST /api/resumes/{resume_id}/analyze`
- `GET /api/resumes/{resume_id}/analysis`
- `DELETE /api/resumes/{resume_id}`

### AI Agent

- `POST /api/agent/run`
- `GET /api/agent/jobs`
- `POST /api/agent/apply`
- `POST /api/agent/apply/{application_id}`

`POST /api/agent/run` discovers and matches jobs without saving them. `POST /api/agent/apply` is used by the AutoApply action: it saves the selected job and tracking record first, then uses the configured Greenhouse API for Greenhouse listings or browser automation for other listings. The read-only submission status changes to `applied` only after the integration confirms submission; otherwise it stays `ready` internally and is not included in the applications list. Opening the external listing does not save an application. Employer-side stages such as review or interview are not currently synchronized from Greenhouse.

### Applications

- `GET /api/applications` (returns confirmed `applied` submissions only)

## Security notes

- Passwords are stored as bcrypt hashes.
- Protected endpoints require a JWT bearer token.
- Resume access is restricted to the authenticated user's records.
- Resume filenames are replaced with server-generated UUID names.
- Resume uploads are limited to 10 MB.
- `.env` and uploaded resume files should not be committed to Git.
