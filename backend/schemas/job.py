from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class JobBase(BaseModel):
    conv_id: str = Field(..., alias="conversation_id")
    owner_message_id: str
    state: str = Field("running", pattern="^(pending|running|done|error)$")
    error: Optional[str] = None

class JobCreate(JobBase):
    pass

class Job(JobBase):
    id: str
    started_at: datetime
    finished_at: Optional[datetime]

    class Config:
        orm_mode = True 