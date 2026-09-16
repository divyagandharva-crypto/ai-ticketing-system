from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class TicketBase(BaseModel):
    title: str
    description: str
    status: str = "open"
    priority: str = "medium"

class TicketCreate(TicketBase):
    pass

class Ticket(TicketBase):
    id: int
    created_by: Optional[int]
    assigned_to: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[str] = None

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: int
    ticket_id: int
    user_id: int
    created_at: datetime

class CommentOut(BaseModel):
    id: int
    content: str
    class Config:
        from_attributes = True  # orm_mode in older pydantic

class TicketWithCommentsOut(BaseModel):
    id: int
    title: str
    comments: list[CommentOut] = []
    class Config:
        from_attributes = True
    class Config:
        orm_mode = True