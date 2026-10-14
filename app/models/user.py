from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    user: Mapped[User | None] = relationship("User")


class CoachProfile(Base):
    __tablename__ = "coach_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    user: Mapped[User | None] = relationship("User")
