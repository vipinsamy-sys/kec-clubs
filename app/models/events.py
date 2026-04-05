from datetime import date, time

from pydantic import BaseModel, ConfigDict


class CreateEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    description: str | None = None
    venue: str | None = None
    date: date
    time: time
    club: list[str] | None = None
