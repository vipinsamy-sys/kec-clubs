import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes.users import router as users_router
from app.routes.admin import router as admins_router
from app.routes.faculty import router as faculty_router
from app.routes.events import router as create_router
from app.routes.clubs import router as clubs_router
from app.database.database import init_db

app = FastAPI()


@app.on_event("startup")
def _startup() -> None:
    init_db()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router, prefix="/api/users")
app.include_router(admins_router, prefix="/api/admins")
app.include_router(faculty_router, prefix="/api/faculty")
app.include_router(create_router, prefix="/api/events")
app.include_router(clubs_router, prefix="/api/clubs")

@app.get("/")
@app.get("/index.html")
def home():
    return FileResponse("public/index.html")

@app.get("/admin-login.html")
def admin_login():
    return FileResponse("public/admin-login.html")

@app.get("/clubs.html")
def club():
    return FileResponse("public/clubs.html")

@app.get("/society.html")
def society():
    return FileResponse("public/society.html")

@app.get("/contact.html")
def contact():
    return FileResponse("public/contact.html")

@app.get("/about.html")
def about():
    return FileResponse("public/about.html")

@app.get("/faculty-login.html")
def faculty_login():
    return FileResponse("public/faculty-login.html")

@app.get("/student-login.html")
def student_login():
    return FileResponse("public/student-login.html")


@app.get("/register.html")
def register():
    return FileResponse("public/register.html")
@app.get("/student-dashboard")
@app.get("/student-dashboard.html")
def student_dashboard():
    return FileResponse("public/student-dashboard.html")

@app.get("/admin-dashboard.html")
def admin_dashboard():
    return FileResponse("public/admin-dashboard.html")

@app.get("/faculty-dashboard.html")
def faculty_dashboard():
    return FileResponse("public/faculty-dashboard.html")