from pydantic import BaseModel, ConfigDict


class admin_loginData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password: str
