import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Club, Event
from app.models.events import CreateEvent


router = APIRouter()

@router.post("/create-event")
def create_event(event: CreateEvent, request: Request, db: Session = Depends(get_db)):
    club_value = (event.club[0] if event.club else None)
    club_id: uuid.UUID | None = None
    if club_value:
        try:
            club_id = uuid.UUID(str(club_value))
        except ValueError:
            club = db.query(Club).filter(Club.club_name == str(club_value)).first()
            if club:
                club_id = club.id
            else:
                raise HTTPException(status_code=400, detail="Invalid club")

    event_dt = datetime.combine(event.date, event.time)
    event_dt = event_dt.replace(tzinfo=timezone.utc)

    faculty_id_cookie = request.cookies.get("faculty_id")
    created_by: uuid.UUID | None = None
    if faculty_id_cookie:
        try:
            created_by = uuid.UUID(faculty_id_cookie)
        except ValueError:
            created_by = None

    db_event = Event(
        title=event.title,
        description=event.description,
        club_id=club_id,
        venue=event.venue,
        event_date=event_dt,
        created_by=created_by,
        approval_status="approved",
    )
    db.add(db_event)
    db.commit()

    return {"message": "Event created successfully", "event_id": str(db_event.id)}



@router.get("/all_events")
def all_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return [
        {
            "_id": str(e.id),
            "event_id": str(e.id),
            "title": e.title,
            "description": e.description,
            "venue": e.venue,
            "date": e.event_date.date().isoformat() if e.event_date else None,
            "time": e.event_date.time().isoformat(timespec="minutes") if e.event_date else None,
        }
        for e in events
    ]
        

