from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False, index=True)
    description = Column(Text, nullable=True)
    due_date = Column(String(64), nullable=True)
    tags = Column(String(512), nullable=True)
    priority = Column(Integer, nullable=True, default=0)
