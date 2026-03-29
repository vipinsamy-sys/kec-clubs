import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import (
    Club,
    ClubStudentCoordinator,
    Event,
    EventRegistration,
    Faculty,
    User,
)
from app.models.faculty import PromotionData, RemoveAdminData, faculty_loginData


router = APIRouter()


def _event_status(event_dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    try:
        return "upcoming" if event_dt >= now else "past"
    except TypeError:
        naive_now = datetime.now()
        return "upcoming" if event_dt >= naive_now else "past"


def _serialize_event(event: Event, registrations_count: int) -> dict:
    event_dt = event.event_date
    return {
        "_id": str(event.id),
        "event_id": str(event.id),
        "title": event.title,
        "description": event.description,
        "venue": event.venue,
        "date": event_dt.date().isoformat() if event_dt else None,
        "time": event_dt.time().isoformat(timespec="minutes") if event_dt else None,
        "status": _event_status(event_dt) if event_dt else "upcoming",
        "current_participants": registrations_count,
        "registered_users": [],
        "max_participants": None,
        "points": 0,
        "club": [str(event.club_id)] if event.club_id else [],
    }


@router.post("/faculty-login")
def login_faculty(faculty: faculty_loginData, response: Response, db: Session = Depends(get_db)):
    db_faculty = db.query(Faculty).filter(Faculty.email == faculty.email).first()
    if not db_faculty:
        raise HTTPException(status_code=400, detail="User not found")

    if db_faculty.password != faculty.password:
        raise HTTPException(status_code=400, detail="Invalid password")

    response.set_cookie(key="faculty_id", value=str(db_faculty.id), httponly=True, samesite="lax")
    return {
        "message": "logged in successfully",
        "faculty": {"name": db_faculty.name, "email": db_faculty.email, "role": "faculty"},
    }


@router.get("/all_events")
def get_all_events(db: Session = Depends(get_db)):
    rows = (
        db.query(Event, func.count(EventRegistration.id))
        .outerjoin(EventRegistration, EventRegistration.event_id == Event.id)
        .group_by(Event.id)
        .all()
    )
    events = [_serialize_event(event, int(count)) for event, count in rows]
    return {"count": len(events), "events": events}


@router.get("/events-dashboard")
def get_upcoming_events(db: Session = Depends(get_db)):
    rows = (
        db.query(Event, func.count(EventRegistration.id))
        .outerjoin(EventRegistration, EventRegistration.event_id == Event.id)
        .group_by(Event.id)
        .all()
    )
    events = [_serialize_event(event, int(count)) for event, count in rows]
    upcoming = [e for e in events if e.get("status") == "upcoming"]
    return {"count": len(upcoming), "events": upcoming}


@router.get("/events-past")
def get_past_events(db: Session = Depends(get_db)):
    rows = (
        db.query(Event, func.count(EventRegistration.id))
        .outerjoin(EventRegistration, EventRegistration.event_id == Event.id)
        .group_by(Event.id)
        .all()
    )
    events = [_serialize_event(event, int(count)) for event, count in rows]
    past = [e for e in events if e.get("status") == "past"]
    return {"count": len(past), "events": past}


@router.get("/event_participants")
@router.get("/event-participants")
def get_event_participants_list(event_id: str, db: Session = Depends(get_db)):
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_id")

    event = db.query(Event).filter(Event.id == event_uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participants = (
        db.query(User)
        .join(EventRegistration, EventRegistration.student_id == User.id)
        .filter(EventRegistration.event_id == event_uuid)
        .all()
    )

    payload = [
        {
            "name": p.name,
            "email": p.email,
            "user_roll": p.register_number,
            "roll_number": p.register_number,
            "department": p.department,
            "year": None,
            "club": None,
        }
        for p in participants
    ]
    return {
        "event_id": event_id,
        "event_title": event.title,
        "count": len(payload),
        "participants": payload,
    }


@router.get("/filter-participants")
def filter_participants(
    club: str | None = None,
    department: str | None = None,
    year: str | None = None,
    month: int | None = None,
    week: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if department:
        query = query.filter(User.department == department)
    users = query.all()
    students = [
        {
            "name": u.name,
            "email": u.email,
            "user_roll": u.register_number,
            "roll_number": u.register_number,
            "department": u.department,
            "year": None,
            "club": None,
        }
        for u in users
    ]
    return {"count": len(students), "students": students}


@router.get("/departments")
def get_departments(db: Session = Depends(get_db)):
    departments = [row[0] for row in db.query(User.department).distinct().all()]
    return {"departments": sorted([d for d in departments if d])}


@router.get("/get-students")
def get_all_students(db: Session = Depends(get_db)):
    students = db.query(User).order_by(User.name.asc()).all()
    return [
        {
            "_id": str(s.id),
            "id": str(s.id),
            "name": s.name,
            "email": s.email,
            "studentId": s.register_number,
            "department": s.department,
            "year": None,
            "club": None,
        }
        for s in students
    ]


@router.post("/promote-admin")
def promote_student_to_admin(
    promotion_data: PromotionData,
    db: Session = Depends(get_db),
    faculty_id: str | None = Cookie(default=None),
):
    if not faculty_id:
        raise HTTPException(status_code=401, detail="Faculty not logged in")

    try:
        faculty_uuid = uuid.UUID(faculty_id)
        student_uuid = uuid.UUID(promotion_data.studentId)
        club_uuid = uuid.UUID(promotion_data.clubId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IDs")

    student = db.query(User).filter(User.id == student_uuid).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    club = db.query(Club).filter(Club.id == club_uuid).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    coordinator = ClubStudentCoordinator(
        student_id=student_uuid,
        club_id=club_uuid,
        assigned_by=faculty_uuid,
    )
    db.add(coordinator)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Already admin for this club")

    return {"message": "Student promoted to admin", "is_admin": True}


@router.post("/remove-admin")
def remove_admin(
    admin_data: RemoveAdminData,
    db: Session = Depends(get_db),
):
    try:
        student_or_coord_uuid = uuid.UUID(admin_data.studentId)
        club_uuid = uuid.UUID(admin_data.clubId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IDs")

    # Frontend sometimes passes admin._id (coordinator row id) instead of studentId.
    row = (
        db.query(ClubStudentCoordinator)
        .filter(
            ClubStudentCoordinator.student_id == student_or_coord_uuid,
            ClubStudentCoordinator.club_id == club_uuid,
        )
        .first()
    )
    if not row:
        row = (
            db.query(ClubStudentCoordinator)
            .filter(
                ClubStudentCoordinator.id == student_or_coord_uuid,
                ClubStudentCoordinator.club_id == club_uuid,
            )
            .first()
        )
    if not row:
        raise HTTPException(status_code=404, detail="Admin record not found")

    removed_student_id = row.student_id
    db.delete(row)
    db.commit()

    still_admin = (
        db.query(ClubStudentCoordinator)
        .filter(ClubStudentCoordinator.student_id == removed_student_id)
        .first()
        is not None
    )
    return {"message": "Admin removed successfully", "is_admin": bool(still_admin)}


@router.get("/get-admins")
def get_all_admins(db: Session = Depends(get_db)):
    rows = (
        db.query(ClubStudentCoordinator, User, Club)
        .join(User, User.id == ClubStudentCoordinator.student_id)
        .join(Club, Club.id == ClubStudentCoordinator.club_id)
        .all()
    )
    return [
        {
            "_id": str(coord.id),
            "studentId": str(student.id),
            "name": student.name,
            "email": student.email,
            "clubId": str(club.id),
            "clubName": club.club_name,
            "role": "admin",
            "status": "active",
        }
        for coord, student, club in rows
    ]
