import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Event, EventRegistration as EventRegistrationModel, User, ClubStudentCoordinator
from app.models.users import EventRegistration, UserRegister, User_loginData

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
    status = _event_status(event_dt)
    date_str = event_dt.date().isoformat() if event_dt else None
    time_str = event_dt.time().isoformat(timespec="minutes") if event_dt else None

    return {
        "_id": str(event.id),
        "event_id": str(event.id),
        "title": event.title,
        "description": event.description,
        "venue": event.venue,
        "date": date_str,
        "time": time_str,
        "status": status,
        "current_participants": registrations_count,
        "registered_users": [],
        "max_participants": None,
        "points": 0,
        "club": [str(event.club_id)] if event.club_id else [],
        "certificates": [],
    }



@router.post("/register")
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user = User(
        name=user.name,
        email=user.email,
        password=user.password,
        role="student",
        department=getattr(user, "dept", None),
        register_number=getattr(user, "user_roll", None),
        mobile_number=str(getattr(user, "user_number", "")) if getattr(user, "user_number", None) else None,
    )
    db.add(db_user)
    db.commit()
    return {"message": "User registered successfully"}

@router.post("/student-login")
def login_user(user: User_loginData, response: Response, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    if db_user.password != user.password:
        raise HTTPException(status_code=400, detail="Invalid password")

    is_admin = (
        db.query(ClubStudentCoordinator)
        .filter(ClubStudentCoordinator.student_id == db_user.id)
        .first()
        is not None
    )

    response.set_cookie(key="user_id", value=str(db_user.id), httponly=True, samesite="lax")

    return {
        "message": "User logged in successfully",
        "user": {
            "user_id": str(db_user.id),
            "name": db_user.name,
            "email": db_user.email,
            "is_admin": bool(is_admin),
        },
    }


@router.get("/events-dashboard")
def get_upcoming_events(db: Session = Depends(get_db)):
    rows = (
        db.query(Event, func.count(EventRegistrationModel.id))
        .outerjoin(EventRegistrationModel, EventRegistrationModel.event_id == Event.id)
        .group_by(Event.id)
        .all()
    )
    events = [_serialize_event(event, int(count)) for event, count in rows]
    upcoming = [e for e in events if e.get("status") == "upcoming"]
    return {"count": len(upcoming), "events": upcoming}

@router.get("/all_events")
def get_all_events(db: Session = Depends(get_db)):
    rows = (
        db.query(Event, func.count(EventRegistrationModel.id))
        .outerjoin(EventRegistrationModel, EventRegistrationModel.event_id == Event.id)
        .group_by(Event.id)
        .all()
    )
    events = [_serialize_event(event, int(count)) for event, count in rows]
    return {"count": len(events), "events": events}

@router.get("/events-past")
def get_past_events(user_id: str | None = None, db: Session = Depends(get_db)):
    if user_id:
        try:
            student_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id")

        rows = (
            db.query(Event, func.count(EventRegistrationModel.id))
            .join(EventRegistrationModel, EventRegistrationModel.event_id == Event.id)
            .filter(EventRegistrationModel.student_id == student_uuid)
            .group_by(Event.id)
            .all()
        )
        events = [_serialize_event(event, int(count)) for event, count in rows]
        return {"count": len(events), "events": events}

    rows = (
        db.query(Event, func.count(EventRegistrationModel.id))
        .outerjoin(EventRegistrationModel, EventRegistrationModel.event_id == Event.id)
        .group_by(Event.id)
        .all()
    )
    events = [_serialize_event(event, int(count)) for event, count in rows]
    past = [e for e in events if e.get("status") == "past"]
    return {"count": len(past), "events": past}

@router.post("/register-event")
def register_event(registration: EventRegistration, db: Session = Depends(get_db)):
    try:
        student_uuid = uuid.UUID(registration.user_id)
        event_uuid = uuid.UUID(registration.event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id or event_id")

    user = db.query(User).filter(User.id == student_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    event = db.query(Event).filter(Event.id == event_uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    reg = EventRegistrationModel(event_id=event.id, student_id=user.id)
    db.add(reg)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Already registered")

    return {"message": "User registered successfully"}


@router.get("/coordinator/events")
@router.get("/coordinator/my-events")
def coordinator_events(
    user_id: str | None = None,
    cookie_user_id: str | None = Cookie(default=None, alias="user_id"),
    db: Session = Depends(get_db),
):
    effective_user_id = user_id or cookie_user_id
    if not effective_user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    try:
        student_uuid = uuid.UUID(effective_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    coord = (
        db.query(ClubStudentCoordinator)
        .filter(ClubStudentCoordinator.student_id == student_uuid)
        .first()
    )
    if not coord:
        return {"count": 0, "events": []}

    rows = (
        db.query(Event, func.count(EventRegistrationModel.id))
        .outerjoin(EventRegistrationModel, EventRegistrationModel.event_id == Event.id)
        .filter(Event.club_id == coord.club_id)
        .group_by(Event.id)
        .all()
    )
    events = [_serialize_event(event, int(count)) for event, count in rows]
    return {"count": len(events), "events": events}


@router.get("/coordinator/participants")
def coordinator_event_participants(
    event_id: str,
    cookie_user_id: str | None = Cookie(default=None, alias="user_id"),
    db: Session = Depends(get_db),
):
    if not cookie_user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    try:
        student_uuid = uuid.UUID(cookie_user_id)
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IDs")

    coord = (
        db.query(ClubStudentCoordinator)
        .filter(ClubStudentCoordinator.student_id == student_uuid)
        .first()
    )
    if not coord:
        raise HTTPException(status_code=403, detail="Not a coordinator")

    event = db.query(Event).filter(Event.id == event_uuid, Event.club_id == coord.club_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participants = (
        db.query(User)
        .join(EventRegistrationModel, EventRegistrationModel.student_id == User.id)
        .filter(EventRegistrationModel.event_id == event_uuid)
        .all()
    )
    payload = [
        {
            "name": p.name,
            "email": p.email,
            "user_roll": p.register_number,
            "roll_number": p.register_number,
            "department": p.department,
        }
        for p in participants
    ]
    return {"event_id": event_id, "event_title": event.title, "count": len(payload), "participants": payload}

