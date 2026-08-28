import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, Text, UniqueConstraint, JSON, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class Centre(Base):
    __tablename__ = 'centres'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200)); branch: Mapped[str | None] = mapped_column(String(200))
    parent_history_days: Mapped[int] = mapped_column(Integer, default=7)
    timezone: Mapped[str] = mapped_column(String(64), default='Pacific/Auckland')
    sleep_check_minutes: Mapped[int] = mapped_column(Integer, default=10)
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
    type: Mapped[str] = mapped_column(String(40), index=True); visibility: Mapped[str] = mapped_column(String(20), default='parent', index=True); effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); performed_by_id: Mapped[str | None] = mapped_column(ForeignKey('staff.id')); recorded_by_id: Mapped[str | None] = mapped_column(ForeignKey('staff.id')); device_id: Mapped[str | None] = mapped_column(ForeignKey('devices.id')); client_id: Mapped[str] = mapped_column(String(80)); operation_id: Mapped[str | None] = mapped_column(String(80), index=True); data: Mapped[dict] = mapped_column(JSON, default=dict); revision: Mapped[int] = mapped_column(Integer, default=1); finalised: Mapped[bool] = mapped_column(Boolean, default=False)
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

class AppSession(Base):
    __tablename__ = 'app_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    centre_id: Mapped[str] = mapped_column(ForeignKey('centres.id'), index=True)
    subject_type: Mapped[str] = mapped_column(String(20), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
class LoginAttempt(Base):
    __tablename__ = 'login_attempts'; __table_args__=(UniqueConstraint('scope','key','window_start'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); scope: Mapped[str] = mapped_column(String(30)); key: Mapped[str] = mapped_column(String(255)); window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True)); count: Mapped[int] = mapped_column(Integer,default=0)
class SleepSession(Base):
    __tablename__='sleep_sessions'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); child_id: Mapped[str]=mapped_column(ForeignKey('children.id'),index=True); room_id: Mapped[str]=mapped_column(ForeignKey('rooms.id')); put_down_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); fell_asleep_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); woke_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); got_up_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); quality: Mapped[str|None]=mapped_column(String(40)); wake_state: Mapped[str|None]=mapped_column(String(40)); wake_reason: Mapped[str|None]=mapped_column(String(100)); note: Mapped[str|None]=mapped_column(Text); check_interval_minutes: Mapped[int]=mapped_column(Integer,default=10); opened_by_staff_id: Mapped[str]=mapped_column(ForeignKey('staff.id')); closed_by_staff_id: Mapped[str|None]=mapped_column(ForeignKey('staff.id')); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class SleepCheck(Base):
    __tablename__='sleep_checks'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); sleep_session_id: Mapped[str]=mapped_column(ForeignKey('sleep_sessions.id'),index=True); child_id: Mapped[str]=mapped_column(ForeignKey('children.id')); room_id: Mapped[str]=mapped_column(ForeignKey('rooms.id')); checked_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); staff_id: Mapped[str]=mapped_column(ForeignKey('staff.id')); warmth: Mapped[str]=mapped_column(String(40),default='normal'); breathing: Mapped[str]=mapped_column(String(40),default='normal'); wellbeing: Mapped[str]=mapped_column(String(40),default='well'); note: Mapped[str|None]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class DomainOperation(Base):
    __tablename__='domain_operations'; __table_args__=(UniqueConstraint('centre_id','domain','client_operation_id',name='uq_domain_operation'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); domain: Mapped[str]=mapped_column(String(40)); client_operation_id: Mapped[str]=mapped_column(String(80)); result: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class MedicationAuthority(Base):
    __tablename__='medication_authorities'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); child_id: Mapped[str]=mapped_column(ForeignKey('children.id'),index=True); medication_name: Mapped[str]=mapped_column(String(200)); form: Mapped[str|None]=mapped_column(String(100)); concentration: Mapped[str|None]=mapped_column(String(100)); dose: Mapped[str]=mapped_column(String(100)); route: Mapped[str]=mapped_column(String(100)); frequency: Mapped[str|None]=mapped_column(String(200)); scheduled_times: Mapped[dict]=mapped_column(JSON,default=list); starts_on: Mapped[str|None]=mapped_column(String(10)); ends_on: Mapped[str|None]=mapped_column(String(10)); storage: Mapped[str|None]=mapped_column(String(200)); instructions: Mapped[str|None]=mapped_column(Text); category: Mapped[str]=mapped_column(String(12)); status: Mapped[str]=mapped_column(String(30),default='draft'); signer_name: Mapped[str|None]=mapped_column(String(200)); revision: Mapped[int]=mapped_column(Integer,default=1); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class MedicationReceipt(Base):
    __tablename__='medication_receipts'; __table_args__=(Index('uq_active_medication_receipt','authority_id',unique=True,sqlite_where=text('returned_at IS NULL'),postgresql_where=text('returned_at IS NULL')),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); authority_id: Mapped[str]=mapped_column(ForeignKey('medication_authorities.id'),index=True); received_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); handed_by: Mapped[str|None]=mapped_column(String(200)); received_by_id: Mapped[str]=mapped_column(ForeignKey('staff.id')); label_checked: Mapped[bool]=mapped_column(Boolean,default=False); authority_matched: Mapped[bool]=mapped_column(Boolean,default=False); expiry_checked: Mapped[bool]=mapped_column(Boolean,default=False); storage_location: Mapped[str|None]=mapped_column(String(200)); quantity: Mapped[str|None]=mapped_column(String(100)); note: Mapped[str|None]=mapped_column(Text); returned_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); returned_to: Mapped[str|None]=mapped_column(String(200)); returned_by_id: Mapped[str|None]=mapped_column(ForeignKey('staff.id'))
class MedicationAdministration(Base):
    __tablename__='medication_administrations'; __table_args__=(UniqueConstraint('centre_id','client_operation_id',name='uq_medication_administration_operation'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); authority_id: Mapped[str]=mapped_column(ForeignKey('medication_authorities.id')); child_id: Mapped[str]=mapped_column(ForeignKey('children.id')); client_operation_id: Mapped[str|None]=mapped_column(String(80)); administered_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); staff_id: Mapped[str]=mapped_column(ForeignKey('staff.id')); outcome: Mapped[str]=mapped_column(String(40)); dose: Mapped[str]=mapped_column(String(100)); note: Mapped[str|None]=mapped_column(Text); finalised: Mapped[bool]=mapped_column(Boolean,default=True); revision: Mapped[int]=mapped_column(Integer,default=1)
class Incident(Base):
    __tablename__='incidents'; __table_args__=(UniqueConstraint('centre_id','client_draft_id',name='uq_incident_draft_operation'),UniqueConstraint('centre_id','finalise_operation_id',name='uq_incident_finalise_operation'))
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); child_id: Mapped[str]=mapped_column(ForeignKey('children.id'),index=True); room_id: Mapped[str]=mapped_column(ForeignKey('rooms.id')); client_draft_id: Mapped[str|None]=mapped_column(String(80)); finalise_operation_id: Mapped[str|None]=mapped_column(String(80)); effective_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); environment: Mapped[str|None]=mapped_column(String(20)); location: Mapped[str|None]=mapped_column(String(200)); incident_type: Mapped[str]=mapped_column(String(80)); other_child_id: Mapped[str|None]=mapped_column(ForeignKey('children.id')); skin_broken: Mapped[bool]=mapped_column(Boolean,default=False); description: Mapped[str|None]=mapped_column(Text); status: Mapped[str]=mapped_column(String(20),default='draft'); revision: Mapped[int]=mapped_column(Integer,default=1); created_by_id: Mapped[str]=mapped_column(ForeignKey('staff.id')); finalised_by_id: Mapped[str|None]=mapped_column(ForeignKey('staff.id')); finalised_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class IncidentBodyArea(Base):
    __tablename__='incident_body_areas'; __table_args__=(UniqueConstraint('incident_id','area'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); incident_id: Mapped[str]=mapped_column(ForeignKey('incidents.id')); area: Mapped[str]=mapped_column(String(40))
class IncidentAction(Base):
    __tablename__='incident_actions'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); incident_id: Mapped[str]=mapped_column(ForeignKey('incidents.id')); action_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); description: Mapped[str]=mapped_column(Text); staff_id: Mapped[str]=mapped_column(ForeignKey('staff.id'))
class Signature(Base):
    __tablename__='signatures'; __table_args__=(UniqueConstraint('domain_type','domain_id','revision','purpose','signer_name'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); centre_id: Mapped[str]=mapped_column(ForeignKey('centres.id'),index=True); parent_id: Mapped[str|None]=mapped_column(ForeignKey('parents.id')); signer_name: Mapped[str]=mapped_column(String(200)); relationship: Mapped[str|None]=mapped_column(String(100)); domain_type: Mapped[str]=mapped_column(String(40)); domain_id: Mapped[str]=mapped_column(String(36)); revision: Mapped[int]=mapped_column(Integer); purpose: Mapped[str]=mapped_column(String(100)); signature_data: Mapped[str]=mapped_column(Text); signed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
