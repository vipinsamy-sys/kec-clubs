from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Club


router = APIRouter()


def _serialize_club(club: Club) -> dict:
    return {
        "_id": str(club.id),
        "id": str(club.id),
        "name": club.club_name,
        "club_name": club.club_name,
        "description": club.description,
        "department": club.department,
    }


@router.get("")
@router.get("/")
def list_clubs(db: Session = Depends(get_db)):
    clubs = db.query(Club).order_by(Club.club_name.asc()).all()
    return [_serialize_club(c) for c in clubs]

@router.get("/all_clubs")
def get_all_clubs(db: Session = Depends(get_db)):
    clubs = db.query(Club).order_by(Club.club_name.asc()).all()
    payload = [_serialize_club(c) for c in clubs]
    return {"count": len(payload), "clubs": payload}





