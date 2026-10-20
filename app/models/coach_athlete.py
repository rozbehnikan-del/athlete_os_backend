from datetime import datetime
from uuid import UUID as PyUUID
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class CoachAthlete(Base):
    __tablename__ = 'coach_athletes'
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    coach_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'))
    athlete_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
