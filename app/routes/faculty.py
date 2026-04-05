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


def _safe_user_year(user: User) -> str | None:
    # Prefer explicit year field if model/data provides one.
    year_value = getattr(user, "year", None)
    if year_value not in (None, ""):
        return str(year_value)

    # Fallback: infer from register number admission year prefix (e.g. 25CSR001 -> 2025).
    reg = (user.register_number or "").strip()
    if len(reg) >= 2 and reg[:2].isdigit():
        admission_year = 2000 + int(reg[:2])
        current_year = datetime.now().year
        derived = current_year - admission_year 
        if 1 <= derived <= 8:
            return str(derived)
    return None


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
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    # 1) Resolve club constraint (supports club UUID or club name).
    club_ids: list[uuid.UUID] | None = None
    if club:
        club_ids = []
        try:
            club_ids = [uuid.UUID(club)]
        except ValueError:
            matched = (
                db.query(Club.id)
                .filter(func.lower(Club.club_name) == club.strip().lower())
                .all()
            )
            club_ids = [row[0] for row in matched if row and row[0]]

        if not club_ids:
            return {"count": 0, "students": [], "events_count": 0, "events": []}

    # 2) Build event query first (events are primary in report output).
    events_query = db.query(Event)

    if club_ids:
        events_query = events_query.filter(Event.club_id.in_(club_ids))

    if start_date:
        try:
            start_dt = datetime.fromisoformat(f"{start_date}T00:00:00")
            events_query = events_query.filter(Event.event_date >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

    if end_date:
        try:
            end_dt = datetime.fromisoformat(f"{end_date}T23:59:59")
            events_query = events_query.filter(Event.event_date <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    events = events_query.order_by(Event.event_date.asc()).all()
    if not events:
        return {"count": 0, "students": [], "events_count": 0, "events": []}

    event_ids = [e.id for e in events]
    event_by_id = {str(e.id): e for e in events}

    club_name_by_id = {
        str(c.id): c.club_name
        for c in db.query(Club).all()
    }

    # 3) Fetch participants for the selected events and apply user filters.
    rows = (
        db.query(EventRegistration, User)
        .join(User, EventRegistration.student_id == User.id)
        .filter(EventRegistration.event_id.in_(event_ids))
        .all()
    )

    normalized_year = year.strip() if year else None

    event_participant_count: dict[str, int] = {str(e.id): 0 for e in events}
    students: list[dict] = []

    for reg, user in rows:
        if department and (user.department or "") != department:
            continue

        user_year = _safe_user_year(user)
        if normalized_year and user_year != normalized_year:
            continue

        event_id_str = str(reg.event_id)
        event = event_by_id.get(event_id_str)
        if not event:
            continue

        event_participant_count[event_id_str] = event_participant_count.get(event_id_str, 0) + 1

        students.append(
            {
                "name": user.name,
                "email": user.email,
                "user_roll": user.register_number,
                "roll_number": user.register_number,
                "department": user.department,
                "year": user_year,
                "club": club_name_by_id.get(str(event.club_id), None),
                "event_id": event_id_str,
                "event_title": event.title,
                "event_date": event.event_date.date().isoformat() if event.event_date else None,
            }
        )

    events_payload = []
    for event in events:
        event_id_str = str(event.id)
        events_payload.append(
            {
                "event_id": event_id_str,
                "title": event.title,
                "date": event.event_date.date().isoformat() if event.event_date else None,
                "venue": event.venue,
                "club": club_name_by_id.get(str(event.club_id), None),
                "participants_count": event_participant_count.get(event_id_str, 0),
            }
        )

    return {
        "count": len(students),
        "students": students,
        "events_count": len(events_payload),
        "events": events_payload,
    }


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
