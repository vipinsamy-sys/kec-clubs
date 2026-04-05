from pydantic import BaseModel, ConfigDict


class faculty_loginData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str


class PromotionData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    studentId: str
    clubId: str


class RemoveAdminData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    studentId: str
    clubId: str
