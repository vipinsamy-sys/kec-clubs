from pydantic import BaseModel, ConfigDict


class UserRegister(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    email: str
    password: str
    user_number: int | None = None
    user_roll: str | None = None
    dept: str | None = None
    year: str | None = None


class User_loginData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str


class EventRegistration(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    event_id: str
