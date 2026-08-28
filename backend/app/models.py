import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class Centre(Base):
    __tablename__ = 'centres'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200)); branch: Mapped[str | None] = mapped_column(String(200))
    parent_history_days: Mapped[int] = mapped_column(Integer, default=7)
class Room(Base):
    __tablename__ = 'rooms'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True)
    name: Mapped[str] = mapped_column(String(100)); accent: Mapped[str] = mapped_column(String(20), default='#176b5b'); icon: Mapped[str] = mapped_column(String(40), default='🌿')
class Staff(Base):
    __tablename__ = 'staff'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True)
    first_name: Mapped[str] = mapped_column(String(100)); last_name: Mapped[str] = mapped_column(String(100)); preferred_name: Mapped[str | None] = mapped_column(String(100))
    employment_type: Mapped[str] = mapped_column(String(40), default='permanent'); active: Mapped[bool] = mapped_column(Boolean, default=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255))
class Account(Base):
    __tablename__ = 'accounts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True); password_hash: Mapped[str] = mapped_column(String(255)); role: Mapped[str] = mapped_column(String(30), default='admin'); active: Mapped[bool] = mapped_column(Boolean, default=True)
class Child(Base):
    __tablename__ = 'children'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True); room_id: Mapped[str | None] = mapped_column(ForeignKey('rooms.id'))
    first_name: Mapped[str] = mapped_column(String(100)); last_name: Mapped[str] = mapped_column(String(100), default=''); preferred_name: Mapped[str | None] = mapped_column(String(100)); dob: Mapped[str | None] = mapped_column(String(10)); active: Mapped[bool] = mapped_column(Boolean, default=True)
class Parent(Base):
    __tablename__ = 'parents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True); name: Mapped[str] = mapped_column(String(200)); login: Mapped[str] = mapped_column(String(100), unique=True); pin_hash: Mapped[str] = mapped_column(String(255)); active: Mapped[bool] = mapped_column(Boolean, default=True)
class ParentChild(Base):
    __tablename__ = 'parent_children'; __table_args__ = (UniqueConstraint('parent_id','child_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); parent_id: Mapped[str] = mapped_column(ForeignKey('parents.id'), index=True); child_id: Mapped[str] = mapped_column(ForeignKey('children.id'), index=True)
class Attendance(Base):
    __tablename__ = 'attendance'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True); child_id: Mapped[str] = mapped_column(ForeignKey('children.id')); room_id: Mapped[str | None] = mapped_column(ForeignKey('rooms.id')); arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); visit_room_id: Mapped[str | None] = mapped_column(ForeignKey('rooms.id')); visit_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); visit_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
class Event(Base):
    __tablename__ = 'events'; __table_args__ = (UniqueConstraint('centre_id','client_id', name='uq_event_client'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True); room_id: Mapped[str | None] = mapped_column(ForeignKey('rooms.id'), index=True); child_id: Mapped[str] = mapped_column(ForeignKey('children.id'), index=True)
    type: Mapped[str] = mapped_column(String(40), index=True); effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); performed_by_id: Mapped[str | None] = mapped_column(ForeignKey('staff.id')); recorded_by_id: Mapped[str | None] = mapped_column(ForeignKey('staff.id')); device_id: Mapped[str | None] = mapped_column(ForeignKey('devices.id')); client_id: Mapped[str] = mapped_column(String(80)); data: Mapped[dict] = mapped_column(JSON, default=dict); revision: Mapped[int] = mapped_column(Integer, default=1); finalised: Mapped[bool] = mapped_column(Boolean, default=False)
class Device(Base):
    __tablename__ = 'devices'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True); label: Mapped[str] = mapped_column(String(120)); default_room_id: Mapped[str | None] = mapped_column(ForeignKey('rooms.id')); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); revoked: Mapped[bool] = mapped_column(Boolean, default=False)
class Pairing(Base):
    __tablename__ = 'pairings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id')); room_id: Mapped[str | None] = mapped_column(ForeignKey('rooms.id')); token_hash: Mapped[str] = mapped_column(String(255), unique=True); challenge: Mapped[str] = mapped_column(String(6)); expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True)); consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
class Audit(Base):
    __tablename__ = 'audits'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True); entity: Mapped[str] = mapped_column(String(50)); entity_id: Mapped[str] = mapped_column(String(36)); action: Mapped[str] = mapped_column(String(50)); before: Mapped[dict | None] = mapped_column(JSON); after: Mapped[dict | None] = mapped_column(JSON); actor_id: Mapped[str | None] = mapped_column(String(36)); reason: Mapped[str | None] = mapped_column(Text); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class ParentNote(Base):
    __tablename__ = 'parent_notes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True); child_id: Mapped[str] = mapped_column(ForeignKey('children.id')); body: Mapped[str] = mapped_column(Text); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); pinned: Mapped[bool] = mapped_column(Boolean, default=False)
