from pydantic import BaseModel, validator
from typing import Optional, List

class TodoBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[int] = 0

class TodoCreate(TodoBase):
    pass

class TodoRead(TodoBase):
    id: int

    @validator("tags", pre=True)
    def ensure_list(cls, v):
        
        if v is None:
            return []
        if isinstance(v, str):
            if v.strip() == "":
                return []
            return [t.strip() for t in v.split(",") if t.strip()]
        if isinstance(v, list):
            return v
        return []

    class Config:
        orm_mode = True
