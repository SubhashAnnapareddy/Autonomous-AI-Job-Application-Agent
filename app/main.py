from fastapi import Depends, FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.agent import router as agent_router
from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.contact import router as contact_router
from app.api.profiles import router as profiles_router
from app.api.resumes import router as resumes_router
from app.database.connection import get_db


app = FastAPI(
    title="EasyApply",
    description="Agentic AI system for job discovery, matching, resume selection and application tracking.",
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(resumes_router)
app.include_router(agent_router)
app.include_router(applications_router)
app.include_router(contact_router)


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "EasyApply"}


@app.get("/database-test", tags=["System"])
def database_test(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))
    return {"database": "connected", "result": result.scalar()}


@app.get("/", tags=["Pages"])
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/register", tags=["Pages"])
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={})


@app.get("/login", tags=["Pages"])
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})


@app.get("/dashboard", tags=["Pages"])
def dashboard_page(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={})


@app.get("/ai-jobs", tags=["Pages"])
def ai_jobs_page(request: Request):
    return templates.TemplateResponse(request=request, name="ai_jobs.html", context={})


@app.get("/profiles", tags=["Pages"])
def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={})


@app.get("/profile", tags=["Pages"])
def profile_alias(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={})


@app.get("/profile/update", tags=["Pages"])
def profile_update_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile_update.html", context={})


@app.get("/applications", tags=["Pages"])
def applications_page(request: Request):
    return templates.TemplateResponse(request=request, name="applications.html", context={})


@app.get("/resumes", tags=["Pages"])
def resumes_page(request: Request):
    return templates.TemplateResponse(request=request, name="resumes.html", context={})


@app.get("/contact", tags=["Pages"])
def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html", context={})
