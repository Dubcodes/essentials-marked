import os, secrets, hashlib, json, re, io, base64
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Response, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, model_validator
from passlib.context import CryptContext
from sqlalchemy import select, func, delete, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_db
from .models import Centre, Room, Staff, Account, Child, Parent, ParentChild, Event, Attendance, RoomVisit, Device, Pairing, Audit, ParentNote, ParentDataRequest, AppSession, LoginAttempt, SleepSession, SleepCheck, DomainOperation, MedicationAuthority, MedicationReceipt, MedicationAdministration, Incident, IncidentBodyArea, IncidentAction, Signature, now

app = FastAPI(title='Essentials Marked', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173').split(','), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
# bcrypt is a deliberately supported adaptive password/PIN hash. Its actual
# deployment configuration is documented; secrets never enter domain payloads.
pwd = CryptContext(schemes=['bcrypt'], deprecated='auto')
SECRET = os.getenv('SECRET_KEY','development-only-change-me')
secure_cookie = os.getenv('COOKIE_SECURE','false').lower() == 'true'
APP_ENV = os.getenv('APP_ENV','development')
MEDIA_DIR = os.getenv('MEDIA_DIR','./media')

@app.middleware('http')
async def csrf_origin_guard(request: Request, call_next):
    if APP_ENV=='production' and request.method in {'POST','PUT','PATCH','DELETE'}:
        origin=request.headers.get('origin'); allowed=os.getenv('PUBLIC_ORIGIN','').rstrip('/')
        if origin and origin.rstrip('/') != allowed: return JSONResponse({'detail':'Cross-site request blocked'},status_code=403)
    return await call_next(request)

def utc(value): return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
def issue_session(response: Response, kind: str, subject_id: str, centre_id: str, minutes: int):
    raw=secrets.token_urlsafe(48); expiry=now()+timedelta(minutes=minutes)
    from .db import SessionLocal
    db=SessionLocal()
    try:
        db.add(AppSession(centre_id=centre_id,subject_type=kind,subject_id=subject_id,token_hash=hashlib.sha256(raw.encode()).hexdigest(),expires_at=expiry));db.commit()
    finally: db.close()
    # The server-side expiry is the authority. A longer browser cookie permits
    # active sessions to slide; an inactive/revoked session still fails closed.
    response.set_cookie(kind,raw,httponly=True,samesite='strict',secure=secure_cookie,max_age=max(minutes*60,31536000),path='/')
def claim(request: Request, kind: str, db: Session):
    raw = request.cookies.get(kind)
    if not raw: raise HTTPException(401, 'Sign in required')
    session=db.scalar(select(AppSession).where(AppSession.token_hash==hashlib.sha256(raw.encode()).hexdigest(),AppSession.subject_type==kind))
    if not session or session.revoked_at or utc(session.expires_at)<=now(): raise HTTPException(401,'Session expired')
    # Sliding inactivity expiry, bounded only by revocation rather than static JWT.
    minutes={'device':10080,'parent':43200,'admin':720}.get(kind,720)
    session.last_active_at=now();session.expires_at=now()+timedelta(minutes=minutes);db.commit()
    return session
def admin(request: Request, db: Session=Depends(get_db)):
    session=claim(request,'admin',db); a=db.get(Account,session.subject_id)
    if not a or not a.active: raise HTTPException(401,'Session revoked')
    return a
def parent(request: Request, db: Session=Depends(get_db)):
    session=claim(request,'parent',db); p=db.get(Parent,session.subject_id)
    if not p or not p.active: raise HTTPException(401,'Session revoked')
    return p
def device(request: Request, db: Session=Depends(get_db)):
    session=claim(request,'device',db); d=db.get(Device,session.subject_id)
    if not d or d.revoked: raise HTTPException(401,'Device session revoked')
    d.last_active_at=now(); db.commit(); return d
def scoped(db, cls, centre_id): return db.scalars(select(cls).where(cls.centre_id==centre_id))
def enforce_failure_limit(db: Session, scope: str, key: str):
    """Check recent credential failures for a server-derived identifier."""
    cutoff=now()-timedelta(minutes=10); start=now().replace(second=0,microsecond=0)
    attempts=db.scalar(select(func.coalesce(func.sum(LoginAttempt.count),0)).where(LoginAttempt.scope==scope,LoginAttempt.key==key,LoginAttempt.window_start>=cutoff))
    if attempts>=8: raise HTTPException(429,'Too many attempts; try later')
    return start
def record_auth_failure(db: Session, scope: str, key: str):
    start=enforce_failure_limit(db,scope,key)
    row=db.scalar(select(LoginAttempt).where(LoginAttempt.scope==scope,LoginAttempt.key==key,LoginAttempt.window_start==start))
    if not row: row=LoginAttempt(scope=scope,key=key,window_start=start,count=0);db.add(row);db.flush()
    row.count+=1;db.commit()
def clear_auth_failures(db: Session, scope: str, key: str):
    db.execute(delete(LoginAttempt).where(LoginAttempt.scope==scope,LoginAttempt.key==key));db.commit()
def verify_staff_pin(db:Session,staff:Staff,pin:str|None,detail:str):
    enforce_failure_limit(db,'staff_pin',staff.id)
    if not pin or not staff.pin_hash or not pwd.verify(pin,staff.pin_hash):record_auth_failure(db,'staff_pin',staff.id);raise HTTPException(403,detail)
    clear_auth_failures(db,'staff_pin',staff.id)
def request_fingerprint(material:dict):
    canonical=json.dumps(material,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=lambda value:value.isoformat())
    return hashlib.sha256(canonical.encode()).hexdigest()
def audit(db, centre, entity, entity_id, action, before=None, after=None, actor=None, reason=None): db.add(Audit(centre_id=centre,entity=entity,entity_id=entity_id,action=action,before=before,after=after,actor_id=actor,reason=reason))
def public_child(c): return {'id':c.id,'first_name':c.preferred_name or c.first_name,'last_name':c.last_name,'room_id':c.room_id}
def clean_domain_data(value):
    if isinstance(value,dict): return {k:clean_domain_data(v) for k,v in value.items() if 'pin' not in k.lower() and 'password' not in k.lower() and 'token' not in k.lower()}
    if isinstance(value,list): return [clean_domain_data(v) for v in value]
    return value
def room_for_device(db, d, room_id):
    room=db.scalar(select(Room).where(Room.id==room_id,Room.centre_id==d.centre_id))
    if not room: raise HTTPException(404,'Room not found for this centre')
    return room


def verify_admin_password(db:Session,a:Account,password:str):
    enforce_failure_limit(db,'admin_confirm',a.id)
    if not password or not pwd.verify(password,a.password_hash):
        record_auth_failure(db,'admin_confirm',a.id)
        raise HTTPException(403,'Admin password incorrect')
    clear_auth_failures(db,'admin_confirm',a.id)

class Login(BaseModel): email: str; password: str
class ParentLogin(BaseModel): login: str; pin: str = Field(pattern=r'^\d{6}$')
class EventIn(BaseModel): client_id: str = Field(min_length=10,max_length=80); child_ids: list[str] = Field(min_length=1,max_length=50); type: Literal['nappy','toilet','food','sunscreen','staff_note','supply']; room_id: str; effective_at: datetime | None=None; performed_by_id: str | None=None; data: dict = Field(default_factory=dict)
class PairIn(BaseModel): room_id: str | None=None; label: str=Field(min_length=2,max_length=120)
class PairComplete(BaseModel): token: str; challenge: str
class Correction(BaseModel): performed_by_id: str; reason: str=Field(min_length=3,max_length=500)
class PresenceIn(BaseModel): child_id: str; room_id:str; action: Literal['arrive','depart','visit','end_visit']; staff_id:str|None=None; effective_at:datetime|None=None
class NoteIn(BaseModel): child_id: str; body: str=Field(min_length=1,max_length=1500)
class ParentNoteAction(BaseModel): read:bool|None=None; pinned:bool|None=None
class RoomIn(BaseModel): name: str=Field(min_length=2,max_length=100); accent: str='#176b5b'; icon: str='🌿'
class SleepIn(BaseModel): client_id:str=Field(min_length=10,max_length=80); child_ids:list[str]=Field(min_length=1,max_length=50); room_id:str; action:Literal['put_down','fell_asleep','wake','got_up','check']; effective_at:datetime|None=None; staff_id:str; warmth:str='normal'; breathing:str='normal'; wellbeing:str='well'; note:str|None=None; quality:str|None=None; wake_state:str|None=None
class MedicationAuthorityIn(BaseModel):
    child_id:str; medication_name:str; dose:str; route:str; category:Literal['i','ii']; form:str|None=None; concentration:str|None=None; frequency:str|None=None; scheduled_times:list[str]=[]; starts_on:date|None=None; ends_on:date|None=None; instructions:str|None=None; signer_name:str|None=None
    @model_validator(mode='after')
    def valid_treatment_range(self):
        if self.starts_on and self.ends_on and self.ends_on<self.starts_on:raise ValueError('end date must be on or after start date')
        return self
class MedicationReceiptIn(BaseModel): authority_id:str; staff_id:str; handed_by:str|None=None; label_checked:bool; authority_matched:bool; expiry_checked:bool; storage_location:str|None=None; quantity:str|None=None; note:str|None=None
class MedicationReturnIn(BaseModel): staff_id:str; returned_to:str=Field(min_length=2,max_length=200)
class MedicationAdminIn(BaseModel): client_operation_id:str=Field(min_length=10,max_length=80); authority_id:str; room_id:str; staff_id:str; staff_pin:str; outcome:Literal['given','refused','partly_taken','spat_out','vomited_afterward','missed','parent_administered','other']; dose:str; note:str|None=None; administered_at:datetime|None=None
class FoodRowIn(BaseModel): child_id:str; food:str|None=None; servings:list[float]=[]; total_servings:float=0; enjoyment:str|None=None
class FoodBatchIn(BaseModel): client_operation_id:str=Field(min_length=10,max_length=80); room_id:str; staff_id:str; effective_at:datetime|None=None; meal:str; description:str|None=None; rows:list[FoodRowIn]=Field(min_length=1,max_length=50)
class IncidentActionIn(BaseModel): action_at:datetime|None=None; description:str=Field(min_length=1,max_length=1000)
class IncidentIn(BaseModel): client_draft_id:str=Field(min_length=10,max_length=80); incident_id:str|None=None; finalise_operation_id:str|None=Field(default=None,min_length=10,max_length=80); child_id:str; room_id:str; staff_id:str; effective_at:datetime|None=None; environment:Literal['indoor','outdoor']|None=None; location:str|None=None; incident_type:str=''; other_child_id:str|None=None; skin_broken:bool=False; description:str|None=None; body_areas:list[str]=[]; actions:list[IncidentActionIn|str]=[]; staff_pin:str|None=None; finalise:bool=False
class SignatureIn(BaseModel): signer_name:str=Field(min_length=2,max_length=200); relationship:str|None=None; signature_data:str=Field(min_length=12,max_length=500000); purpose:str=Field(min_length=2,max_length=100)
class DataRequestIn(BaseModel): child_id:str; start_date:date; end_date:date; note:str|None=Field(default=None,max_length=1500)
class DataRequestAction(BaseModel): status:Literal['new','in_progress','completed','declined']
class BrandingIn(BaseModel): display_name:str|None=Field(default=None,max_length=200); secondary_text:str|None=Field(default=None,max_length=240); timezone:str|None=Field(default=None,max_length=80)

class RoomAdminIn(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    accent:str=Field(default='#176b5b',pattern=r'^#[0-9A-Fa-f]{6}$')
    icon:str=Field(default='??',min_length=1,max_length=40)

class RoomDeleteIn(BaseModel):
    admin_password:str=Field(min_length=1,max_length=300)

class StaffAdminCreateIn(BaseModel):
    first_name:str=Field(min_length=1,max_length=100)
    last_name:str=Field(min_length=1,max_length=100)
    preferred_name:str|None=Field(default=None,max_length=100)
    employment_type:str=Field(default='permanent',min_length=2,max_length=40)
    active:bool=True
    pin:str|None=Field(default=None,pattern=r'^\d{4}$')

class StaffAdminUpdateIn(BaseModel):
    first_name:str|None=Field(default=None,min_length=1,max_length=100)
    last_name:str|None=Field(default=None,min_length=1,max_length=100)
    preferred_name:str|None=Field(default=None,max_length=100)
    employment_type:str|None=Field(default=None,min_length=2,max_length=40)
    active:bool|None=None

class StaffPinResetIn(BaseModel):
    admin_password:str=Field(min_length=1,max_length=300)
    pin:str=Field(pattern=r'^\d{4}$')

class ChildAdminCreateIn(BaseModel):
    first_name:str=Field(min_length=1,max_length=100)
    last_name:str=Field(default='',max_length=100)
    preferred_name:str|None=Field(default=None,max_length=100)
    dob:str|None=Field(default=None,pattern=r'^\d{4}-\d{2}-\d{2}$')
    room_id:str|None=None
    active:bool=True

class ChildAdminUpdateIn(BaseModel):
    first_name:str|None=Field(default=None,min_length=1,max_length=100)
    last_name:str|None=Field(default=None,max_length=100)
    preferred_name:str|None=Field(default=None,max_length=100)
    dob:str|None=Field(default=None,pattern=r'^\d{4}-\d{2}-\d{2}$')
    room_id:str|None=None
    active:bool|None=None

@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/auth/admin/login')
def admin_login(body: Login, response: Response, request: Request, db: Session=Depends(get_db)):
    key=body.email.lower();enforce_failure_limit(db,'admin',key);a=db.scalar(select(Account).where(Account.email==key))
    if not a or not pwd.verify(body.password,a.password_hash):record_auth_failure(db,'admin',key);raise HTTPException(401,'Invalid credentials')
    clear_auth_failures(db,'admin',key)
    issue_session(response,'admin',a.id,a.centre_id,720)
    return {'centre_id':a.centre_id,'role':a.role}
@app.post('/api/auth/parent/login')
def parent_login(body: ParentLogin,response: Response,request:Request,db:Session=Depends(get_db)):
    key=body.login.lower();enforce_failure_limit(db,'parent',key);p=db.scalar(select(Parent).where(Parent.login==key))
    if not p or not pwd.verify(body.pin,p.pin_hash):record_auth_failure(db,'parent',key);raise HTTPException(401,'Invalid login or PIN')
    clear_auth_failures(db,'parent',key)
    issue_session(response,'parent',p.id,p.centre_id,43200)
    return {'ok':True}
@app.post('/api/auth/logout')
def logout(request:Request,response:Response,db:Session=Depends(get_db)):
    for k in ('admin','parent','device'):
        raw=request.cookies.get(k)
        if raw:
            row=db.scalar(select(AppSession).where(AppSession.token_hash==hashlib.sha256(raw.encode()).hexdigest()))
            if row:row.revoked_at=now()
        response.delete_cookie(k)
    db.commit()
    return {'ok':True}

@app.get('/api/admin/bootstrap')
def bootstrap(a:Account=Depends(admin),db:Session=Depends(get_db)):
    c=db.get(Centre,a.centre_id)

    attendance={
        x.child_id:x
        for x in db.scalars(
            select(Attendance).where(
                Attendance.centre_id==a.centre_id,
                Attendance.departed_at.is_(None)
            )
        )
    }

    rooms=list(scoped(db,Room,a.centre_id))
    room_names={r.id:r.name for r in rooms}

    child_models=list(scoped(db,Child,a.centre_id))
    children=[]

    for child in child_models:
        row=attendance.get(child.id)

        physical=(
            row.visit_room_id
            if row and row.visit_room_id and row.visit_ended_at is None
            else child.room_id
        )

        children.append({
            'id':child.id,
            'first_name':child.first_name,
            'last_name':child.last_name,
            'preferred_name':child.preferred_name,
            'display_name':child.preferred_name or child.first_name,
            'dob':child.dob,
            'room_id':child.room_id,
            'active':child.active,
            'present':bool(row),
            'arrived_at':row.arrived_at if row else None,
            'physical_room_id':physical,
            'physical_room':room_names.get(physical),
            'enrolled_room':room_names.get(child.room_id)
        })

    room_data=[]

    for room in rooms:
        room_data.append({
            'id':room.id,
            'name':room.name,
            'accent':room.accent,
            'icon':room.icon,
            'enrolled_count':sum(
                1
                for child in child_models
                if child.active and child.room_id==room.id
            ),
            'present_count':sum(
                1
                for child in children
                if child['present'] and child['physical_room_id']==room.id
            )
        })

    staff=[]

    for item in scoped(db,Staff,a.centre_id):
        staff.append({
            'id':item.id,
            'first_name':item.first_name,
            'last_name':item.last_name,
            'preferred_name':item.preferred_name,
            'name':(
                (item.preferred_name or item.first_name)
                +' '
                +item.last_name[:1]
                +'.'
            ),
            'employment_type':item.employment_type,
            'active':item.active
        })

    requests=list(
        db.scalars(
            select(ParentDataRequest)
            .where(ParentDataRequest.centre_id==a.centre_id)
            .order_by(ParentDataRequest.created_at.desc())
        )
    )

    return {
        'centre':{
            'id':c.id,
            'name':c.name,
            'branch':c.branch,
            'parent_history_days':c.parent_history_days,
            'timezone':c.timezone,
            'display_name':c.display_name,
            'secondary_text':c.secondary_text,
            'logo_url':(
                f'/api/branding/{c.id}/logo'
                if c.logo_path
                else None
            )
        },
        'rooms':room_data,
        'staff':staff,
        'children':children,
        'families':db.scalar(
            select(func.count())
            .select_from(Parent)
            .where(Parent.centre_id==a.centre_id)
        ),
        'devices':[
            {
                'id':x.id,
                'label':x.label,
                'default_room_id':x.default_room_id,
                'default_room':room_names.get(x.default_room_id),
                'last_active_at':x.last_active_at,
                'revoked':x.revoked
            }
            for x in scoped(db,Device,a.centre_id)
        ],
        'incident_drafts':db.scalar(
            select(func.count())
            .select_from(Incident)
            .where(
                Incident.centre_id==a.centre_id,
                Incident.status=='draft'
            )
        ),
        'data_requests':[
            {
                'id':x.id,
                'child_id':x.child_id,
                'child_name':(
                    db.get(Child,x.child_id).preferred_name
                    or db.get(Child,x.child_id).first_name
                ),
                'start_date':x.start_date,
                'end_date':x.end_date,
                'note':x.note,
                'status':x.status,
                'created_at':x.created_at
            }
            for x in requests
        ],
        'demo_mode':(
            os.getenv('DEMO_SEED','false').lower()=='true'
        )
    }

@app.post('/api/admin/rooms')
def create_room(
    body:RoomAdminIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    room=Room(
        centre_id=a.centre_id,
        name=body.name.strip(),
        accent=body.accent.upper(),
        icon=body.icon.strip()
    )

    db.add(room)
    db.flush()

    audit(
        db,
        a.centre_id,
        'room',
        room.id,
        'created',
        after={
            'name':room.name,
            'accent':room.accent,
            'icon':room.icon
        },
        actor=a.id
    )

    db.commit()

    return {
        'id':room.id,
        'name':room.name,
        'accent':room.accent,
        'icon':room.icon
    }


@app.patch('/api/admin/rooms/{room_id}')
def update_room(
    room_id:str,
    body:RoomAdminIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    room=db.scalar(
        select(Room).where(
            Room.id==room_id,
            Room.centre_id==a.centre_id
        )
    )

    if not room:
        raise HTTPException(404,'Room not found')

    before={
        'name':room.name,
        'accent':room.accent,
        'icon':room.icon
    }

    room.name=body.name.strip()
    room.accent=body.accent.upper()
    room.icon=body.icon.strip()

    audit(
        db,
        a.centre_id,
        'room',
        room.id,
        'updated',
        before=before,
        after={
            'name':room.name,
            'accent':room.accent,
            'icon':room.icon
        },
        actor=a.id
    )

    db.commit()

    return {
        'id':room.id,
        'name':room.name,
        'accent':room.accent,
        'icon':room.icon
    }


@app.post('/api/admin/rooms/{room_id}/delete')
def delete_room(
    room_id:str,
    body:RoomDeleteIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    verify_admin_password(db,a,body.admin_password)

    room=db.scalar(
        select(Room).where(
            Room.id==room_id,
            Room.centre_id==a.centre_id
        )
    )

    if not room:
        raise HTTPException(404,'Room not found')

    references={
        'children':db.scalar(
            select(func.count())
            .select_from(Child)
            .where(Child.room_id==room.id)
        ),
        'devices':db.scalar(
            select(func.count())
            .select_from(Device)
            .where(Device.default_room_id==room.id)
        ),
        'attendance':db.scalar(
            select(func.count())
            .select_from(Attendance)
            .where(
                or_(
                    Attendance.room_id==room.id,
                    Attendance.visit_room_id==room.id,
                    Attendance.last_visit_room_id==room.id
                )
            )
        ),
        'room visits':db.scalar(
            select(func.count())
            .select_from(RoomVisit)
            .where(RoomVisit.room_id==room.id)
        ),
        'care records':db.scalar(
            select(func.count())
            .select_from(Event)
            .where(Event.room_id==room.id)
        ),
        'sleep sessions':db.scalar(
            select(func.count())
            .select_from(SleepSession)
            .where(SleepSession.room_id==room.id)
        ),
        'sleep checks':db.scalar(
            select(func.count())
            .select_from(SleepCheck)
            .where(SleepCheck.room_id==room.id)
        ),
        'pairings':db.scalar(
            select(func.count())
            .select_from(Pairing)
            .where(Pairing.room_id==room.id)
        ),
        'incidents':db.scalar(
            select(func.count())
            .select_from(Incident)
            .where(Incident.room_id==room.id)
        )
    }

    used=[
        name
        for name,count in references.items()
        if count
    ]

    if used:
        raise HTTPException(
            409,
            'Room cannot be permanently deleted because it is used by: '
            +', '.join(used)
            +'. Keep the room for history or move/archive the dependencies first.'
        )

    room_id_copy=room.id
    room_name=room.name

    db.delete(room)

    audit(
        db,
        a.centre_id,
        'room',
        room_id_copy,
        'deleted',
        before={'name':room_name},
        actor=a.id,
        reason='Password-confirmed admin deletion'
    )

    db.commit()

    return {'ok':True}


@app.post('/api/admin/staff')
def create_staff(
    body:StaffAdminCreateIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    staff=Staff(
        centre_id=a.centre_id,
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        preferred_name=(
            body.preferred_name.strip()
            if body.preferred_name
            else None
        ),
        employment_type=body.employment_type.strip(),
        active=body.active,
        pin_hash=(
            pwd.hash(body.pin)
            if body.pin
            else None
        )
    )

    db.add(staff)
    db.flush()

    audit(
        db,
        a.centre_id,
        'staff',
        staff.id,
        'created',
        after={
            'first_name':staff.first_name,
            'last_name':staff.last_name,
            'preferred_name':staff.preferred_name,
            'employment_type':staff.employment_type,
            'active':staff.active,
            'pin_set':bool(body.pin)
        },
        actor=a.id
    )

    db.commit()

    return {'id':staff.id}


@app.patch('/api/admin/staff/{staff_id}')
def update_staff(
    staff_id:str,
    body:StaffAdminUpdateIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    staff=db.scalar(
        select(Staff).where(
            Staff.id==staff_id,
            Staff.centre_id==a.centre_id
        )
    )

    if not staff:
        raise HTTPException(404,'Staff member not found')

    before={
        'first_name':staff.first_name,
        'last_name':staff.last_name,
        'preferred_name':staff.preferred_name,
        'employment_type':staff.employment_type,
        'active':staff.active
    }

    updates=body.model_dump(exclude_unset=True)

    if 'first_name' in updates:
        staff.first_name=updates['first_name'].strip()

    if 'last_name' in updates:
        staff.last_name=updates['last_name'].strip()

    if 'preferred_name' in updates:
        staff.preferred_name=(
            updates['preferred_name'].strip()
            if updates['preferred_name']
            else None
        )

    if 'employment_type' in updates:
        staff.employment_type=updates['employment_type'].strip()

    if 'active' in updates:
        staff.active=updates['active']

    audit(
        db,
        a.centre_id,
        'staff',
        staff.id,
        'updated',
        before=before,
        after={
            'first_name':staff.first_name,
            'last_name':staff.last_name,
            'preferred_name':staff.preferred_name,
            'employment_type':staff.employment_type,
            'active':staff.active
        },
        actor=a.id
    )

    db.commit()

    return {'ok':True}


@app.post('/api/admin/staff/{staff_id}/pin-reset')
def reset_staff_pin(
    staff_id:str,
    body:StaffPinResetIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    verify_admin_password(db,a,body.admin_password)

    staff=db.scalar(
        select(Staff).where(
            Staff.id==staff_id,
            Staff.centre_id==a.centre_id
        )
    )

    if not staff:
        raise HTTPException(404,'Staff member not found')

    staff.pin_hash=pwd.hash(body.pin)

    audit(
        db,
        a.centre_id,
        'staff',
        staff.id,
        'pin_reset',
        after={'pin_reset':True},
        actor=a.id,
        reason='Password-confirmed admin PIN reset'
    )

    db.commit()

    return {'ok':True}


def admin_room(
    db:Session,
    centre_id:str,
    room_id:str|None
):
    if not room_id:
        return None

    room=db.scalar(
        select(Room).where(
            Room.id==room_id,
            Room.centre_id==centre_id
        )
    )

    if not room:
        raise HTTPException(
            422,
            'Choose a valid room for this centre'
        )

    return room


@app.post('/api/admin/children')
def create_child(
    body:ChildAdminCreateIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    admin_room(db,a.centre_id,body.room_id)

    child=Child(
        centre_id=a.centre_id,
        room_id=body.room_id,
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        preferred_name=(
            body.preferred_name.strip()
            if body.preferred_name
            else None
        ),
        dob=body.dob,
        active=body.active
    )

    db.add(child)
    db.flush()

    audit(
        db,
        a.centre_id,
        'child',
        child.id,
        'created',
        after={
            'first_name':child.first_name,
            'last_name':child.last_name,
            'preferred_name':child.preferred_name,
            'dob':child.dob,
            'room_id':child.room_id,
            'active':child.active
        },
        actor=a.id
    )

    db.commit()

    return {'id':child.id}


@app.patch('/api/admin/children/{child_id}')
def update_child(
    child_id:str,
    body:ChildAdminUpdateIn,
    a:Account=Depends(admin),
    db:Session=Depends(get_db)
):
    child=db.scalar(
        select(Child).where(
            Child.id==child_id,
            Child.centre_id==a.centre_id
        )
    )

    if not child:
        raise HTTPException(404,'Child not found')

    before={
        'first_name':child.first_name,
        'last_name':child.last_name,
        'preferred_name':child.preferred_name,
        'dob':child.dob,
        'room_id':child.room_id,
        'active':child.active
    }

    updates=body.model_dump(exclude_unset=True)

    if 'room_id' in updates:
        admin_room(
            db,
            a.centre_id,
            updates['room_id']
        )
        child.room_id=updates['room_id']

    if 'first_name' in updates:
        child.first_name=updates['first_name'].strip()

    if 'last_name' in updates:
        child.last_name=updates['last_name'].strip()

    if 'preferred_name' in updates:
        child.preferred_name=(
            updates['preferred_name'].strip()
            if updates['preferred_name']
            else None
        )

    if 'dob' in updates:
        child.dob=updates['dob']

    if 'active' in updates and updates['active'] is False and child.active:
        open_sleep=db.scalar(
            select(SleepSession.id).where(
                SleepSession.centre_id==a.centre_id,
                SleepSession.child_id==child.id,
                SleepSession.got_up_at.is_(None)
            )
        )

        if open_sleep:
            raise HTTPException(
                409,
                'Record Got up before archiving a child with an open sleep session'
            )

        present=db.scalar(
            select(Attendance.id).where(
                Attendance.centre_id==a.centre_id,
                Attendance.child_id==child.id,
                Attendance.departed_at.is_(None)
            )
        )

        if present:
            raise HTTPException(
                409,
                'Depart the child before archiving them'
            )

    if 'active' in updates:
        child.active=updates['active']

    audit(
        db,
        a.centre_id,
        'child',
        child.id,
        'updated',
        before=before,
        after={
            'first_name':child.first_name,
            'last_name':child.last_name,
            'preferred_name':child.preferred_name,
            'dob':child.dob,
            'room_id':child.room_id,
            'active':child.active
        },
        actor=a.id
    )

    db.commit()

    return {'ok':True}


@app.post('/api/admin/pairings')
def create_pairing(body:PairIn,a:Account=Depends(admin),db:Session=Depends(get_db)):
    if body.room_id and not db.scalar(select(Room).where(Room.id==body.room_id,Room.centre_id==a.centre_id)): raise HTTPException(404,'Room not found')
    raw=secrets.token_urlsafe(32); challenge=str(secrets.randbelow(900)+100); p=Pairing(centre_id=a.centre_id,room_id=body.room_id,label=body.label,token_hash=hashlib.sha256(raw.encode()).hexdigest(),challenge=challenge,expires_at=now()+timedelta(seconds=90));db.add(p);db.commit();origin=os.getenv('PUBLIC_ORIGIN','http://localhost:5173').rstrip('/');url=f'{origin}/classroom/pair?token={raw}'
    try:
        import qrcode
        image=qrcode.make(url);buffer=io.BytesIO();image.save(buffer,format='PNG');qr='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()
    except ImportError:qr=None
    return {'id':p.id,'token':raw,'challenge':challenge,'expires_at':p.expires_at,'label':p.label,'pairing_url':url,'qr_data_url':qr}
@app.get('/api/admin/pairings/{pairing_id}')
def pairing_status(pairing_id:str,a:Account=Depends(admin),db:Session=Depends(get_db)):
    p=db.scalar(select(Pairing).where(Pairing.id==pairing_id,Pairing.centre_id==a.centre_id))
    if not p:raise HTTPException(404,'Pairing not found')
    return {'id':p.id,'label':p.label,'expires_at':p.expires_at,'consumed_at':p.consumed_at,'device_id':p.device_id}
@app.get('/api/admin/events')
def events(day:str|None=None,room_id:str|None=None,staff_id:str|None=None,a:Account=Depends(admin),db:Session=Depends(get_db)):
    q=select(Event).where(Event.centre_id==a.centre_id)
    if room_id:q=q.where(Event.room_id==room_id)
    if staff_id:q=q.where(Event.performed_by_id==staff_id)
    if day:
        local=datetime.fromisoformat(day).date();zone=ZoneInfo(db.get(Centre,a.centre_id).timezone);start=datetime.combine(local,datetime.min.time(),tzinfo=zone).astimezone(timezone.utc);end=datetime.combine(local+timedelta(days=1),datetime.min.time(),tzinfo=zone).astimezone(timezone.utc);q=q.where(Event.effective_at>=start,Event.effective_at<end)
    return [event_out(e,db) for e in db.scalars(q.order_by(Event.created_at.desc()).limit(500))]
@app.patch('/api/admin/events/{event_id}/attribution')
def correct(event_id:str,body:Correction,a:Account=Depends(admin),db:Session=Depends(get_db)):
    e=db.scalar(select(Event).where(Event.id==event_id,Event.centre_id==a.centre_id))
    if not e:raise HTTPException(404,'Record not found')
    if e.type in ('medicine','incident') and e.finalised:raise HTTPException(409,'Finalised high-consequence records require individual revision workflow')
    st=db.scalar(select(Staff).where(Staff.id==body.performed_by_id,Staff.centre_id==a.centre_id))
    if not st:raise HTTPException(404,'Staff not found')
    before={'performed_by_id':e.performed_by_id};e.performed_by_id=st.id;e.updated_at=now();audit(db,a.centre_id,'event',e.id,'attribution_corrected',before,{'performed_by_id':st.id},a.id,body.reason);db.commit();return event_out(e,db)
@app.get('/api/admin/audit')
def audits(a:Account=Depends(admin),db:Session=Depends(get_db)): return [{'id':x.id,'entity':x.entity,'entity_id':x.entity_id,'action':x.action,'before':x.before,'after':x.after,'reason':x.reason,'created_at':x.created_at} for x in db.scalars(select(Audit).where(Audit.centre_id==a.centre_id).order_by(Audit.created_at.desc()).limit(200))]
@app.post('/api/admin/devices/{device_id}/revoke')
def revoke(device_id:str,a:Account=Depends(admin),db:Session=Depends(get_db)):
    d=db.scalar(select(Device).where(Device.id==device_id,Device.centre_id==a.centre_id));
    if not d:raise HTTPException(404,'Device not found')
    d.revoked=True;db.commit();return {'ok':True}
@app.patch('/api/admin/data-requests/{request_id}')
def update_data_request(request_id:str,body:DataRequestAction,a:Account=Depends(admin),db:Session=Depends(get_db)):
    item=db.scalar(select(ParentDataRequest).where(ParentDataRequest.id==request_id,ParentDataRequest.centre_id==a.centre_id))
    if not item:raise HTTPException(404,'Request not found')
    before={'status':item.status};item.status=body.status;item.updated_at=now();item.handled_by_id=a.id;audit(db,a.centre_id,'parent_data_request',item.id,'status_changed',before,{'status':item.status},a.id);db.commit();return {'id':item.id,'status':item.status}
@app.patch('/api/admin/branding')
def update_branding(body:BrandingIn,a:Account=Depends(admin),db:Session=Depends(get_db)):
    centre=db.get(Centre,a.centre_id);centre.display_name=body.display_name or None;centre.secondary_text=body.secondary_text or None
    if body.timezone:
        try:ZoneInfo(body.timezone)
        except Exception:raise HTTPException(422,'Enter a valid IANA timezone, such as Pacific/Auckland')
        centre.timezone=body.timezone
    audit(db,a.centre_id,'centre',centre.id,'branding_updated',actor=a.id);db.commit();return {'display_name':centre.display_name,'secondary_text':centre.secondary_text,'timezone':centre.timezone}
@app.post('/api/admin/branding/logo')
async def upload_branding_logo(file:UploadFile=File(...),a:Account=Depends(admin),db:Session=Depends(get_db)):
    if file.content_type not in {'image/png','image/jpeg','image/webp'}:raise HTTPException(422,'Logo must be PNG, JPEG, or WebP')
    raw=await file.read(5_000_001)
    if len(raw)>5_000_000:raise HTTPException(422,'Logo must be 5 MB or smaller')
    from PIL import Image,UnidentifiedImageError
    try:
        image=Image.open(io.BytesIO(raw));image.verify();image=Image.open(io.BytesIO(raw)).convert('RGBA');image.thumbnail((800,400))
    except (UnidentifiedImageError,OSError):raise HTTPException(422,'Uploaded file is not a valid image')
    os.makedirs(MEDIA_DIR,exist_ok=True);name=f'centre-{a.centre_id}.webp';path=os.path.join(MEDIA_DIR,name);image.save(path,'WEBP',quality=88)
    centre=db.get(Centre,a.centre_id);centre.logo_path=name;audit(db,a.centre_id,'centre',centre.id,'logo_updated',actor=a.id);db.commit();return {'logo_url':f'/api/branding/{centre.id}/logo'}
@app.delete('/api/admin/branding/logo')
def remove_branding_logo(a:Account=Depends(admin),db:Session=Depends(get_db)):
    centre=db.get(Centre,a.centre_id)
    if centre.logo_path:
        path=os.path.join(MEDIA_DIR,os.path.basename(centre.logo_path))
        if os.path.isfile(path):os.remove(path)
    centre.logo_path=None;db.commit();return {'ok':True}
@app.get('/api/branding/{centre_id}/logo')
def branding_logo(centre_id:str,db:Session=Depends(get_db)):
    centre=db.get(Centre,centre_id)
    if not centre or not centre.logo_path:raise HTTPException(404,'Logo not found')
    path=os.path.join(MEDIA_DIR,os.path.basename(centre.logo_path))
    if not os.path.isfile(path):raise HTTPException(404,'Logo not found')
    return FileResponse(path,media_type='image/webp')

@app.post('/api/device/pair')
def pair(body:PairComplete,response:Response,db:Session=Depends(get_db)):
    key=hashlib.sha256(body.token.encode()).hexdigest();enforce_failure_limit(db,'pairing',key)
    p=db.scalar(select(Pairing).where(Pairing.token_hash==key))
    expiry = p.expires_at.replace(tzinfo=timezone.utc) if p and p.expires_at.tzinfo is None else (p.expires_at if p else now())
    if not p or p.consumed_at or expiry<now() or not secrets.compare_digest(p.challenge,body.challenge):record_auth_failure(db,'pairing',key);raise HTTPException(400,'Pairing code invalid or expired')
    clear_auth_failures(db,'pairing',key)
    d=Device(centre_id=p.centre_id,label=p.label,default_room_id=p.room_id);p.consumed_at=now();db.add(d);db.flush();p.device_id=d.id;db.commit();issue_session(response,'device',d.id,d.centre_id,10080);return {'id':d.id,'room_id':d.default_room_id,'label':d.label}
@app.get('/api/classroom/bootstrap')
def classroom_bootstrap(d:Device=Depends(device),db:Session=Depends(get_db)):
    centre=db.get(Centre,d.centre_id);children=list(db.scalars(select(Child).where(Child.centre_id==d.centre_id,Child.active.is_(True)))); active_att={x.child_id:x for x in db.scalars(select(Attendance).where(Attendance.centre_id==d.centre_id,Attendance.arrived_at.is_not(None),Attendance.departed_at.is_(None)))}
    return {'device_id':d.id,'default_room_id':d.default_room_id,'centre':{'id':centre.id,'name':centre.name,'display_name':centre.display_name,'secondary_text':centre.secondary_text,'logo_url':f'/api/branding/{centre.id}/logo' if centre.logo_path else None,'timezone':centre.timezone},'last_confirmed_at':now(),'rooms':[{'id':r.id,'name':r.name,'accent':r.accent,'icon':r.icon} for r in scoped(db,Room,d.centre_id)],'staff':[{'id':s.id,'name':(s.preferred_name or s.first_name)+' '+s.last_name[:1]+'.'} for s in scoped(db,Staff,d.centre_id) if s.active],'children':[public_child(c)|{'present':c.id in active_att,'arrived_at':active_att[c.id].arrived_at if c.id in active_att else None,'visiting_room_id':active_att[c.id].visit_room_id if c.id in active_att and active_att[c.id].visit_ended_at is None else None} for c in children],'unread_notes':db.scalar(select(func.count()).select_from(ParentNote).where(ParentNote.centre_id==d.centre_id,ParentNote.read_at.is_(None))),'incident_drafts':db.scalar(select(func.count()).select_from(Incident).where(Incident.centre_id==d.centre_id,Incident.status=='draft'))}
@app.get('/api/classroom/parent-notes')
def classroom_parent_notes(d:Device=Depends(device),db:Session=Depends(get_db)):
    rows=db.scalars(select(ParentNote).where(ParentNote.centre_id==d.centre_id).order_by(ParentNote.pinned.desc(),ParentNote.created_at.desc()).limit(100))
    return [{'id':n.id,'child_id':n.child_id,'child_name':(db.get(Child,n.child_id).preferred_name or db.get(Child,n.child_id).first_name),'body':n.body,'created_at':n.created_at,'read_at':n.read_at,'pinned':n.pinned} for n in rows]
@app.patch('/api/classroom/parent-notes/{note_id}')
def classroom_parent_note_action(note_id:str,body:ParentNoteAction,d:Device=Depends(device),db:Session=Depends(get_db)):
    note=db.scalar(select(ParentNote).where(ParentNote.id==note_id,ParentNote.centre_id==d.centre_id))
    if not note:raise HTTPException(404,'Parent note not found')
    if body.read is not None:note.read_at=now() if body.read else None
    if body.pinned is not None:note.pinned=body.pinned
    db.commit();return {'id':note.id,'read_at':note.read_at,'pinned':note.pinned}
@app.post('/api/classroom/presence')
def presence(body:PresenceIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    room_for_device(db,d,body.room_id)
    c=db.scalar(select(Child).where(Child.id==body.child_id,Child.centre_id==d.centre_id));
    if not c:raise HTTPException(404,'Child not found')
    staff=staff_for_device(db,d,body.staff_id) if body.staff_id else None;when=body.effective_at or now()
    a=db.scalar(select(Attendance).where(Attendance.child_id==c.id,Attendance.departed_at.is_(None)).order_by(Attendance.arrived_at.desc()))
    if body.action=='arrive':
        if not a:a=Attendance(centre_id=d.centre_id,child_id=c.id,room_id=body.room_id,arrived_at=when,recorded_by_staff_id=staff.id if staff else None,device_id=d.id);db.add(a)
    elif not a: raise HTTPException(409,'Child is not present')
    elif body.action=='depart':
        sleeping=active_sleep(db,d.centre_id,c.id)
        if sleeping:raise HTTPException(409,f'{c.first_name} has an open sleep session ({sleep_state(sleeping).replace("_"," ")}). Record Got up before departure.')
        a.departed_at=when
        if a.visit_room_id:
            visit=db.scalar(select(RoomVisit).where(RoomVisit.attendance_id==a.id,RoomVisit.ended_at.is_(None)).order_by(RoomVisit.started_at.desc()))
            if visit:visit.ended_at=when;visit.ended_by_staff_id=staff.id if staff else None
            a.last_visit_room_id=a.visit_room_id;a.visit_room_id=None;a.visit_ended_at=when
    elif body.action=='visit':
        if a.visit_room_id and a.visit_ended_at is None:raise HTTPException(409,'Child already has an active room visit')
        a.visit_room_id=body.room_id;a.visit_started_at=when;a.visit_ended_at=None;db.add(RoomVisit(centre_id=d.centre_id,attendance_id=a.id,child_id=c.id,room_id=body.room_id,started_at=when,started_by_staff_id=staff.id if staff else None,device_id=d.id))
    else:
        if not a.visit_room_id or a.visit_ended_at is not None:raise HTTPException(409,'Child has no active room visit')
        visit=db.scalar(select(RoomVisit).where(RoomVisit.attendance_id==a.id,RoomVisit.ended_at.is_(None)).order_by(RoomVisit.started_at.desc()))
        if visit:visit.ended_at=when;visit.ended_by_staff_id=staff.id if staff else None
        a.last_visit_room_id=a.visit_room_id;a.visit_room_id=None;a.visit_ended_at=when
    db.flush()
    audit(db,d.centre_id,'attendance',a.id,body.action,after={'child_id':c.id,'room_id':body.room_id,'effective_at':when.isoformat()},actor=staff.id if staff else None)
    db.commit();return {'ok':True,'visiting_room_id':a.visit_room_id}
@app.post('/api/classroom/events')
def create_event(body:EventIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    room_for_device(db,d,body.room_id)
    staff=db.scalar(select(Staff).where(Staff.id==body.performed_by_id,Staff.centre_id==d.centre_id,Staff.active.is_(True))) if body.performed_by_id else None
    if not staff:raise HTTPException(422,'Select a valid active staff member')
    data=clean_domain_data(body.data);material={'child_ids':sorted(set(body.child_ids)),'type':body.type,'room_id':body.room_id,'effective_at':body.effective_at,'performed_by_id':staff.id,'data':data};fingerprint=request_fingerprint(material)
    prior=db.scalar(select(DomainOperation).where(DomainOperation.centre_id==d.centre_id,DomainOperation.domain=='ordinary',DomainOperation.client_operation_id==body.client_id))
    if prior:
        if not prior.request_fingerprint or not secrets.compare_digest(prior.request_fingerprint,fingerprint):raise HTTPException(409,'Operation ID was already used for a different ordinary event request')
        existing=list(db.scalars(select(Event).where(Event.centre_id==d.centre_id,Event.operation_id==body.client_id).order_by(Event.child_id)))
        return {'events':[event_out(x,db) for x in existing],'idempotent':True}
    existing=list(db.scalars(select(Event).where(Event.centre_id==d.centre_id,Event.operation_id==body.client_id).order_by(Event.child_id)))
    if existing:raise HTTPException(409,'Existing operation cannot be safely replayed because its original fingerprint is unavailable')
    children=list(db.scalars(select(Child).where(Child.id.in_(body.child_ids),Child.centre_id==d.centre_id)))
    if len(children)!=len(set(body.child_ids)):raise HTTPException(404,'One or more children not found')
    items=[]
    visibility='staff' if body.type=='staff_note' else 'parent'
    for c in children:
        e=Event(centre_id=d.centre_id,room_id=body.room_id,child_id=c.id,type=body.type,visibility=visibility,effective_at=body.effective_at or now(),performed_by_id=staff.id,recorded_by_id=staff.id,device_id=d.id,client_id=hashlib.sha256(f'{body.client_id}:{c.id}'.encode()).hexdigest(),operation_id=body.client_id,data=data,finalised=False);db.add(e);items.append(e)
    db.add(DomainOperation(centre_id=d.centre_id,domain='ordinary',client_operation_id=body.client_id,request_fingerprint=fingerprint,result={'child_ids':sorted(set(body.child_ids))}))
    try:db.commit()
    except IntegrityError:
        db.rollback();prior=db.scalar(select(DomainOperation).where(DomainOperation.centre_id==d.centre_id,DomainOperation.domain=='ordinary',DomainOperation.client_operation_id==body.client_id))
        if prior and prior.request_fingerprint and secrets.compare_digest(prior.request_fingerprint,fingerprint):
            existing=list(db.scalars(select(Event).where(Event.centre_id==d.centre_id,Event.operation_id==body.client_id).order_by(Event.child_id)));return {'events':[event_out(x,db) for x in existing],'idempotent':True}
        if prior:raise HTTPException(409,'Operation ID was already used for a different ordinary event request')
        raise
    return {'events':[event_out(e,db) for e in items],'idempotent':False}

@app.post('/api/classroom/food-batch')
def food_batch(body:FoodBatchIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    room_for_device(db,d,body.room_id);staff=staff_for_device(db,d,body.staff_id)
    ids=[row.child_id for row in body.rows]
    if len(ids)!=len(set(ids)):raise HTTPException(422,'Each child may appear only once in a food batch')
    children={x.id:x for x in db.scalars(select(Child).where(Child.id.in_(ids),Child.centre_id==d.centre_id))}
    if len(children)!=len(ids):raise HTTPException(404,'One or more children not found')
    canonical=[]
    for row in sorted(body.rows,key=lambda x:x.child_id):
        if any(amount<0 or amount>10 for amount in row.servings):raise HTTPException(422,'Serving amounts are invalid')
        canonical.append({'child_id':row.child_id,'food':row.food or body.description or None,'servings':row.servings,'total_servings':round(sum(row.servings),2),'enjoyment':row.enjoyment})
    material={'room_id':body.room_id,'staff_id':staff.id,'effective_at':body.effective_at,'meal':body.meal,'description':body.description or None,'rows':canonical};fingerprint=request_fingerprint(material)
    prior=db.scalar(select(DomainOperation).where(DomainOperation.centre_id==d.centre_id,DomainOperation.domain=='food_batch',DomainOperation.client_operation_id==body.client_operation_id))
    if prior:
        if not prior.request_fingerprint or not secrets.compare_digest(prior.request_fingerprint,fingerprint):raise HTTPException(409,'Operation ID was already used for a different food batch')
        events=list(db.scalars(select(Event).where(Event.centre_id==d.centre_id,Event.operation_id==body.client_operation_id).order_by(Event.child_id)));return {'events':[event_out(e,db) for e in events],'idempotent':True}
    when=body.effective_at or now();items=[]
    for row in canonical:
        data={'meal':body.meal,'food':row['food'],'servings':row['servings'],'total_servings':row['total_servings'],'enjoyment':row['enjoyment']}
        event=Event(centre_id=d.centre_id,room_id=body.room_id,child_id=row['child_id'],type='food',visibility='parent',effective_at=when,performed_by_id=staff.id,recorded_by_id=staff.id,device_id=d.id,client_id=hashlib.sha256(f'{body.client_operation_id}:{row["child_id"]}'.encode()).hexdigest(),operation_id=body.client_operation_id,data=clean_domain_data(data),finalised=False);db.add(event);items.append(event)
    db.add(DomainOperation(centre_id=d.centre_id,domain='food_batch',client_operation_id=body.client_operation_id,request_fingerprint=fingerprint,result={'child_ids':ids}))
    try:db.commit()
    except IntegrityError:
        db.rollback();prior=db.scalar(select(DomainOperation).where(DomainOperation.centre_id==d.centre_id,DomainOperation.domain=='food_batch',DomainOperation.client_operation_id==body.client_operation_id))
        if prior and prior.request_fingerprint and secrets.compare_digest(prior.request_fingerprint,fingerprint):
            events=list(db.scalars(select(Event).where(Event.centre_id==d.centre_id,Event.operation_id==body.client_operation_id).order_by(Event.child_id)));return {'events':[event_out(e,db) for e in events],'idempotent':True}
        if prior:raise HTTPException(409,'Operation ID was already used for a different food batch')
        raise
    return {'events':[event_out(e,db) for e in items],'idempotent':False}

def staff_for_device(db,d,staff_id):
    staff=db.scalar(select(Staff).where(Staff.id==staff_id,Staff.centre_id==d.centre_id,Staff.active.is_(True)))
    if not staff: raise HTTPException(422,'Select a valid active staff member')
    return staff
def active_sleep(db, centre_id, child_id):
    return db.scalar(select(SleepSession).where(SleepSession.centre_id==centre_id,SleepSession.child_id==child_id,SleepSession.got_up_at.is_(None)).order_by(SleepSession.created_at.desc()))
def sleep_state(session):return 'sleeping' if session.fell_asleep_at and not session.woke_at else ('awake_resting' if session.woke_at else 'settling')
def sleep_status(db, session):
    if not session.fell_asleep_at or session.woke_at: return 'green'
    last=db.scalar(select(SleepCheck).where(SleepCheck.sleep_session_id==session.id).order_by(SleepCheck.checked_at.desc()))
    last_at=utc(last.checked_at) if last else utc(session.fell_asleep_at); elapsed=(now()-last_at).total_seconds()/60
    return 'red' if elapsed>session.check_interval_minutes else ('amber' if elapsed>=session.check_interval_minutes*.8 else 'green')

@app.post('/api/classroom/sleep')
def sleep(body:SleepIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    room_for_device(db,d,body.room_id)
    material=body.model_dump(mode='json',exclude={'client_id'});material['child_ids']=sorted(material['child_ids']);fingerprint=request_fingerprint(material)
    prior=db.scalar(select(DomainOperation).where(DomainOperation.centre_id==d.centre_id,DomainOperation.domain=='sleep',DomainOperation.client_operation_id==body.client_id))
    if prior:
        if not prior.request_fingerprint or not secrets.compare_digest(prior.request_fingerprint,fingerprint):raise HTTPException(409,'Operation ID was already used for a different sleep request')
        return {'sessions':prior.result.get('sessions',[]),'idempotent':True}
    staff=staff_for_device(db,d,body.staff_id)
    if body.action=='put_down':
        centre=db.get(Centre,d.centre_id)
        if not 5<=centre.sleep_check_minutes<=10: raise HTTPException(409,'Centre sleep-check interval must be between 5 and 10 minutes')
    children=list(db.scalars(select(Child).where(Child.id.in_(body.child_ids),Child.centre_id==d.centre_id)))
    if len(children)!=len(set(body.child_ids)): raise HTTPException(404,'One or more children not found')
    results=[]
    for child in children:
        session=active_sleep(db,d.centre_id,child.id)
        when=body.effective_at or now()
        if body.action=='put_down':
            if session: raise HTTPException(409,f'{child.first_name} already has an active sleep session')
            centre=db.get(Centre,d.centre_id); session=SleepSession(centre_id=d.centre_id,child_id=child.id,room_id=body.room_id,put_down_at=when,check_interval_minutes=centre.sleep_check_minutes,opened_by_staff_id=staff.id,note=body.note);db.add(session);results.append({'child_id':child.id,'session_id':session.id,'status':'green'})
        else:
            if not session: raise HTTPException(409,f'{child.first_name} has no active sleep session')
            if session.room_id!=body.room_id: raise HTTPException(409,f'{child.first_name} sleep session belongs to a different room')
            if body.action=='fell_asleep':
                if session.fell_asleep_at or session.woke_at: raise HTTPException(409,f'{child.first_name} cannot be marked asleep in the current state')
                if utc(when)<utc(session.put_down_at):raise HTTPException(409,'Fell asleep time cannot be before put down time')
                session.fell_asleep_at=when;session.note=body.note or session.note
            elif body.action=='wake':
                if not session.fell_asleep_at or session.woke_at: raise HTTPException(409,f'{child.first_name} cannot be woken in the current state')
                if utc(when)<utc(session.fell_asleep_at):raise HTTPException(409,'Wake time cannot be before fell asleep time')
                session.woke_at=when;session.wake_state=body.wake_state;session.quality=body.quality;session.note=body.note or session.note
            elif body.action=='got_up':
                if utc(when)<utc(session.put_down_at):raise HTTPException(409,'Got up time cannot be before put down time')
                if session.fell_asleep_at and utc(when)<utc(session.fell_asleep_at):raise HTTPException(409,'Got up time cannot be before fell asleep time')
                if session.woke_at and utc(when)<utc(session.woke_at):raise HTTPException(409,'Got up time cannot be before wake time')
                session.got_up_at=when;session.closed_by_staff_id=staff.id;session.note=body.note or session.note
            else:
                if not session.fell_asleep_at or session.woke_at: raise HTTPException(409,f'{child.first_name} is not currently asleep')
                if utc(when)<utc(session.fell_asleep_at):raise HTTPException(409,'Sleep check time cannot be before fell asleep time')
                previous=db.scalar(select(SleepCheck).where(SleepCheck.sleep_session_id==session.id).order_by(SleepCheck.checked_at.desc()))
                if previous and utc(when)<utc(previous.checked_at):raise HTTPException(409,'Sleep check time cannot be before the previous check')
                db.add(SleepCheck(centre_id=d.centre_id,sleep_session_id=session.id,child_id=child.id,room_id=session.room_id,checked_at=when,staff_id=staff.id,warmth=body.warmth,breathing=body.breathing,wellbeing=body.wellbeing,note=body.note))
            session.updated_at=now();results.append({'child_id':child.id,'session_id':session.id,'status':sleep_status(db,session)})
        if body.action!='check':
            event_id='sleep-'+hashlib.sha256(f'{body.client_id}:{child.id}'.encode()).hexdigest()
            duration_minutes=max(0,round((utc(when)-utc(session.fell_asleep_at)).total_seconds()/60)) if body.action=='wake' and session.fell_asleep_at else None
            db.add(Event(centre_id=d.centre_id,room_id=body.room_id,child_id=child.id,type='sleep',visibility='parent',effective_at=when,performed_by_id=staff.id,recorded_by_id=staff.id,device_id=d.id,client_id=event_id,operation_id=body.client_id,data={'state':body.action.replace('_',' '),'duration_minutes':duration_minutes,'quality':body.quality,'wake_state':body.wake_state,'note':body.note},finalised=True))
    db.add(DomainOperation(centre_id=d.centre_id,domain='sleep',client_operation_id=body.client_id,request_fingerprint=fingerprint,result={'action':body.action,'room_id':body.room_id,'staff_id':body.staff_id,'sessions':results}))
    try: db.commit()
    except IntegrityError:
        db.rollback(); prior=db.scalar(select(DomainOperation).where(DomainOperation.centre_id==d.centre_id,DomainOperation.domain=='sleep',DomainOperation.client_operation_id==body.client_id))
        if prior and prior.request_fingerprint and secrets.compare_digest(prior.request_fingerprint,fingerprint):return {'sessions':prior.result.get('sessions',[]),'idempotent':True}
        if prior:raise HTTPException(409,'Operation ID was already used for a different sleep request')
        raise
    return {'sessions':results,'idempotent':False}

@app.get('/api/classroom/sleep-status')
def classroom_sleep_status(d:Device=Depends(device),db:Session=Depends(get_db)):
    sessions=list(db.scalars(select(SleepSession).where(SleepSession.centre_id==d.centre_id,SleepSession.got_up_at.is_(None))))
    centre=db.get(Centre,d.centre_id);today=now().astimezone(ZoneInfo(centre.timezone)).date();present=set(db.scalars(select(Attendance.child_id).where(Attendance.centre_id==d.centre_id,Attendance.departed_at.is_(None))))
    states=[sleep_status(db,s) for s in sessions]; worst='red' if 'red' in states else ('amber' if 'amber' in states else 'green')
    items=[]
    for s in sessions:
        child=db.get(Child,s.child_id);last=db.scalar(select(SleepCheck).where(SleepCheck.sleep_session_id==s.id).order_by(SleepCheck.checked_at.desc()))
        state=sleep_state(s);last_at=last.checked_at if last else s.fell_asleep_at;next_due=utc(last_at)+timedelta(minutes=s.check_interval_minutes) if last_at and state=='sleeping' else None;stale=utc(s.put_down_at).astimezone(ZoneInfo(centre.timezone)).date()<today or s.child_id not in present
        items.append({'id':s.id,'child_id':s.child_id,'child_name':child.preferred_name or child.first_name,'room_id':s.room_id,'state':state,'status':sleep_status(db,s),'put_down_at':s.put_down_at,'fell_asleep_at':s.fell_asleep_at,'woke_at':s.woke_at,'last_check_at':last.checked_at if last else None,'next_due_at':next_due,'check_interval_minutes':s.check_interval_minutes,'stale':stale,'stale_reason':'Previous sleep needs closing' if stale else None})
    return {'active':len(sessions),'status':worst,'sessions':items}

@app.post('/api/medication/authorities')
def medication_authority(body:MedicationAuthorityIn,a:Account=Depends(admin),db:Session=Depends(get_db)):
    child=db.scalar(select(Child).where(Child.id==body.child_id,Child.centre_id==a.centre_id))
    if not child: raise HTTPException(404,'Child not found')
    authority=MedicationAuthority(centre_id=a.centre_id,child_id=child.id,status='draft',**body.model_dump(exclude={'child_id','signer_name'}))
    db.add(authority);db.commit();return {'id':authority.id,'status':authority.status,'revision':authority.revision}
@app.post('/api/parent/medication-authorities')
def parent_medication_authority(body:MedicationAuthorityIn,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    if not db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==body.child_id)): raise HTTPException(404,'Child not found')
    authority=MedicationAuthority(centre_id=p.centre_id,child_id=body.child_id,status='draft',**body.model_dump(exclude={'child_id','signer_name'}));db.add(authority);db.commit();return {'id':authority.id,'status':authority.status,'revision':authority.revision}
@app.post('/api/parent/medication-authorities/{authority_id}/authorise')
def authorise_medication(authority_id:str,body:SignatureIn,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    authority=db.scalar(select(MedicationAuthority).where(MedicationAuthority.id==authority_id,MedicationAuthority.centre_id==p.centre_id))
    if not authority or not db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==authority.child_id)): raise HTTPException(404,'Medication authority not found')
    if authority.status!='draft': raise HTTPException(409,'Authority has already been actioned')
    authority.status='authorised';authority.signer_name=body.signer_name;authority.updated_at=now();db.add(Signature(centre_id=p.centre_id,parent_id=p.id,signer_name=body.signer_name,relationship=body.relationship,domain_type='medication_authority',domain_id=authority.id,revision=authority.revision,purpose=body.purpose,signature_data=body.signature_data));db.commit();return {'id':authority.id,'status':authority.status}
@app.get('/api/parent/medication-authorities')
def parent_medication_authorities(p:Parent=Depends(parent),db:Session=Depends(get_db)):
    permitted=[x.child_id for x in db.scalars(select(ParentChild).where(ParentChild.parent_id==p.id))]
    return [{'id':m.id,'child_id':m.child_id,'medication_name':m.medication_name,'dose':m.dose,'route':m.route,'category':m.category,'status':m.status,'scheduled_times':m.scheduled_times,'instructions':m.instructions,'revision':m.revision} for m in db.scalars(select(MedicationAuthority).where(MedicationAuthority.centre_id==p.centre_id,MedicationAuthority.child_id.in_(permitted)).order_by(MedicationAuthority.created_at.desc()))]
@app.get('/api/classroom/medications')
def classroom_medications(d:Device=Depends(device),db:Session=Depends(get_db)):
    rows=[]
    for authority in db.scalars(select(MedicationAuthority).where(MedicationAuthority.centre_id==d.centre_id).order_by(MedicationAuthority.created_at.desc())):
        child=db.get(Child,authority.child_id); receipt=db.scalar(select(MedicationReceipt).where(MedicationReceipt.authority_id==authority.id,MedicationReceipt.returned_at.is_(None)).order_by(MedicationReceipt.received_at.desc()))
        latest=db.scalar(select(MedicationReceipt).where(MedicationReceipt.authority_id==authority.id).order_by(MedicationReceipt.received_at.desc()))
        rows.append({'id':authority.id,'child_id':authority.child_id,'child_name':(child.preferred_name or child.first_name),'medication_name':authority.medication_name,'dose':authority.dose,'route':authority.route,'category':authority.category,'scheduled_times':authority.scheduled_times,'instructions':authority.instructions,'status':authority.status,'received':bool(receipt),'receipt_id':receipt.id if receipt else None,'returned_at':latest.returned_at if latest else None})
    return rows
@app.post('/api/medication/receipts')
def medication_receipt(body:MedicationReceiptIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    authority=db.scalar(select(MedicationAuthority).where(MedicationAuthority.id==body.authority_id,MedicationAuthority.centre_id==d.centre_id))
    staff=staff_for_device(db,d,body.staff_id)
    if not authority: raise HTTPException(404,'Medication authority not found')
    if authority.status!='authorised': raise HTTPException(409,'Medication authority has not been authorised by a parent')
    if not (body.label_checked and body.authority_matched and body.expiry_checked): raise HTTPException(422,'All receipt safety checks must be confirmed before medication becomes active')
    if db.scalar(select(MedicationReceipt).where(MedicationReceipt.authority_id==authority.id,MedicationReceipt.returned_at.is_(None))): raise HTTPException(409,'Medication already has an active receipt')
    receipt=MedicationReceipt(centre_id=d.centre_id,authority_id=authority.id,received_by_id=staff.id,**body.model_dump(exclude={'authority_id','staff_id'}));db.add(receipt);db.commit();return {'id':receipt.id}

@app.post('/api/medication/receipts/{receipt_id}/return')
def return_medication(receipt_id:str,body:MedicationReturnIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    staff=staff_for_device(db,d,body.staff_id);receipt=db.scalar(select(MedicationReceipt).where(MedicationReceipt.id==receipt_id,MedicationReceipt.centre_id==d.centre_id))
    if not receipt:raise HTTPException(404,'Medication receipt not found')
    if receipt.returned_at:raise HTTPException(409,'Medication has already been returned')
    receipt.returned_at=now();receipt.returned_to=body.returned_to;receipt.returned_by_id=staff.id;db.commit();return {'id':receipt.id,'returned_at':receipt.returned_at}

def normalised_dose(value:str): return re.sub(r'\s+','',value).casefold()

@app.post('/api/classroom/medication/administrations')
def medication_administration(body:MedicationAdminIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    room_for_device(db,d,body.room_id)
    material=body.model_dump(mode='json',exclude={'client_operation_id','staff_pin'});material['dose']=normalised_dose(body.dose);fingerprint=request_fingerprint(material)
    prior=db.scalar(select(MedicationAdministration).where(MedicationAdministration.centre_id==d.centre_id,MedicationAdministration.client_operation_id==body.client_operation_id))
    if prior:
        if not prior.request_fingerprint or not secrets.compare_digest(prior.request_fingerprint,fingerprint):raise HTTPException(409,'Operation ID was already used for a different administration')
        return {'id':prior.id,'outcome':prior.outcome,'idempotent':True}
    staff=staff_for_device(db,d,body.staff_id)
    verify_staff_pin(db,staff,body.staff_pin,'Incorrect staff PIN — nothing was recorded.')
    authority=db.scalar(select(MedicationAuthority).where(MedicationAuthority.id==body.authority_id,MedicationAuthority.centre_id==d.centre_id,MedicationAuthority.status=='authorised'))
    receipt=db.scalar(select(MedicationReceipt).where(MedicationReceipt.authority_id==body.authority_id,MedicationReceipt.centre_id==d.centre_id,MedicationReceipt.returned_at.is_(None)))
    if not authority or not receipt: raise HTTPException(409,'Medication needs an active authority and confirmed physical receipt')
    centre=db.get(Centre,d.centre_id); administered_at=body.administered_at or now(); local_day=utc(administered_at).astimezone(ZoneInfo(centre.timezone)).date()
    if (authority.starts_on and local_day<authority.starts_on) or (authority.ends_on and local_day>authority.ends_on): raise HTTPException(409,'Administration is outside the authority treatment dates')
    if normalised_dose(body.dose)!=normalised_dose(authority.dose): raise HTTPException(409,'Dose does not exactly match the authorised dose')
    admin=MedicationAdministration(centre_id=d.centre_id,authority_id=authority.id,child_id=authority.child_id,client_operation_id=body.client_operation_id,request_fingerprint=fingerprint,administered_at=administered_at,staff_id=staff.id,outcome=body.outcome,dose=authority.dose,note=body.note)
    event_operation='medicine-'+body.client_operation_id
    db.add(admin);db.flush(); db.add(Event(centre_id=d.centre_id,room_id=body.room_id,child_id=authority.child_id,type='medicine',visibility='parent',effective_at=admin.administered_at,performed_by_id=staff.id,recorded_by_id=staff.id,device_id=d.id,client_id=event_operation,operation_id=event_operation,data={'medication':authority.medication_name,'dose':authority.dose,'route':authority.route,'outcome':body.outcome},finalised=True))
    try:db.commit()
    except IntegrityError:
        db.rollback();prior=db.scalar(select(MedicationAdministration).where(MedicationAdministration.centre_id==d.centre_id,MedicationAdministration.client_operation_id==body.client_operation_id))
        if prior and prior.request_fingerprint and secrets.compare_digest(prior.request_fingerprint,fingerprint):return {'id':prior.id,'outcome':prior.outcome,'idempotent':True}
        if prior:raise HTTPException(409,'Operation ID was already used for a different administration')
        raise
    return {'id':admin.id,'outcome':admin.outcome,'idempotent':False}

@app.post('/api/classroom/incidents')
def incident(body:IncidentIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    room_for_device(db,d,body.room_id);staff=staff_for_device(db,d,body.staff_id)
    finalise_fingerprint=None
    if body.finalise:
        material=body.model_dump(mode='json',exclude={'staff_pin','finalise_operation_id'});material['body_areas']=sorted(set(material['body_areas']));finalise_fingerprint=request_fingerprint(material)
    child=db.scalar(select(Child).where(Child.id==body.child_id,Child.centre_id==d.centre_id));other=db.scalar(select(Child).where(Child.id==body.other_child_id,Child.centre_id==d.centre_id)) if body.other_child_id else None
    if not child or (body.other_child_id and not other):raise HTTPException(404,'Child not found')
    canonical_areas={'head','face','neck','chest','back','abdomen','left_arm','right_arm','left_hand','right_hand','left_leg','right_leg','left_foot','right_foot','other'}
    invalid=set(body.body_areas)-canonical_areas
    if invalid:raise HTTPException(422,'Invalid body area: '+', '.join(sorted(invalid)))
    report=db.scalar(select(Incident).where(Incident.centre_id==d.centre_id,Incident.client_draft_id==body.client_draft_id))
    if body.incident_id and (not report or report.id!=body.incident_id):raise HTTPException(409,'Incident ID does not match this draft operation')
    if report and report.child_id!=child.id:raise HTTPException(409,'Draft operation belongs to a different child')
    if report and report.status=='finalised':
        if body.finalise and report.finalise_operation_id==body.finalise_operation_id and report.finalise_request_fingerprint and secrets.compare_digest(report.finalise_request_fingerprint,finalise_fingerprint):return {'id':report.id,'status':report.status,'revision':report.revision,'idempotent':True}
        raise HTTPException(409,'Incident has already been finalised')
    if body.finalise:
        if not body.incident_type.strip():raise HTTPException(422,'Incident type still needs to be entered.')
        if not body.finalise_operation_id:raise HTTPException(422,'A finalise operation ID is required')
        used=db.scalar(select(Incident).where(Incident.centre_id==d.centre_id,Incident.finalise_operation_id==body.finalise_operation_id))
        if used and (not report or used.id!=report.id):raise HTTPException(409,'Finalise operation ID was already used')
        verify_staff_pin(db,staff,body.staff_pin,'Incorrect staff PIN — incident remains a draft.')
    is_update=report is not None
    if not report:
        report=Incident(centre_id=d.centre_id,client_draft_id=body.client_draft_id,child_id=child.id,room_id=body.room_id,effective_at=body.effective_at or now(),incident_type=body.incident_type,status='draft',created_by_id=staff.id);db.add(report);db.flush()
    report.room_id=body.room_id;report.effective_at=body.effective_at or report.effective_at;report.environment=body.environment;report.location=body.location;report.incident_type=body.incident_type;report.other_child_id=body.other_child_id;report.skin_broken=body.skin_broken;report.description=body.description;report.updated_at=now()
    if is_update:report.revision+=1
    db.execute(delete(IncidentBodyArea).where(IncidentBodyArea.incident_id==report.id));db.execute(delete(IncidentAction).where(IncidentAction.incident_id==report.id))
    for area in set(body.body_areas):db.add(IncidentBodyArea(incident_id=report.id,area=area))
    action_data=[]
    for action in body.actions:
        action_at=(action.action_at if isinstance(action,IncidentActionIn) else None) or now();description=action.description if isinstance(action,IncidentActionIn) else action;db.add(IncidentAction(incident_id=report.id,action_at=action_at,description=description,staff_id=staff.id));action_data.append({'action_at':action_at.isoformat(),'description':description})
    if body.finalise:
        report.status='finalised';report.finalise_operation_id=body.finalise_operation_id;report.finalise_request_fingerprint=finalise_fingerprint;report.finalised_by_id=staff.id;report.finalised_at=now();event_operation='incident-'+body.finalise_operation_id
        db.add(Event(centre_id=d.centre_id,room_id=body.room_id,child_id=child.id,type='incident',visibility='parent',effective_at=report.effective_at,performed_by_id=staff.id,recorded_by_id=staff.id,device_id=d.id,client_id=event_operation,operation_id=event_operation,data={'incident_type':report.incident_type,'skin_broken':report.skin_broken,'description':report.description or '', 'body_areas':body.body_areas,'actions':action_data,'involved':'another child' if report.other_child_id else None},finalised=True))
    try:db.commit()
    except IntegrityError:
        db.rollback();existing=db.scalar(select(Incident).where(Incident.centre_id==d.centre_id,Incident.client_draft_id==body.client_draft_id))
        if existing and existing.child_id==body.child_id and body.finalise and existing.finalise_operation_id==body.finalise_operation_id and existing.finalise_request_fingerprint and secrets.compare_digest(existing.finalise_request_fingerprint,finalise_fingerprint):return {'id':existing.id,'status':existing.status,'revision':existing.revision,'idempotent':True}
        if existing:raise HTTPException(409,'Incident operation conflicts with an existing request')
        raise
    return {'id':report.id,'status':report.status,'revision':report.revision,'idempotent':False}

@app.get('/api/classroom/incidents/drafts')
def incident_drafts(d:Device=Depends(device),db:Session=Depends(get_db)):
    rows=db.scalars(select(Incident).where(Incident.centre_id==d.centre_id,Incident.status=='draft').order_by(Incident.updated_at.desc()))
    output=[]
    for item in rows:
        child=db.get(Child,item.child_id);actions=list(db.scalars(select(IncidentAction).where(IncidentAction.incident_id==item.id).order_by(IncidentAction.action_at)));areas=list(db.scalars(select(IncidentBodyArea.area).where(IncidentBodyArea.incident_id==item.id)))
        output.append({'id':item.id,'client_draft_id':item.client_draft_id,'child_id':item.child_id,'child_name':child.preferred_name or child.first_name,'room_id':item.room_id,'effective_at':item.effective_at,'environment':item.environment,'location':item.location,'incident_type':item.incident_type,'other_child_id':item.other_child_id,'skin_broken':item.skin_broken,'description':item.description,'body_areas':areas,'actions':[{'action_at':x.action_at,'description':x.description} for x in actions],'updated_at':item.updated_at})
    return output
@app.delete('/api/classroom/incidents/drafts/{incident_id}')
def discard_incident_draft(incident_id:str,d:Device=Depends(device),db:Session=Depends(get_db)):
    report=db.scalar(select(Incident).where(Incident.id==incident_id,Incident.centre_id==d.centre_id))
    if not report:raise HTTPException(404,'Incident draft not found')
    if report.status!='draft':raise HTTPException(409,'Finalised incidents cannot be discarded')
    db.execute(delete(IncidentAction).where(IncidentAction.incident_id==report.id));db.execute(delete(IncidentBodyArea).where(IncidentBodyArea.incident_id==report.id));db.delete(report);audit(db,d.centre_id,'incident',incident_id,'draft_discarded',actor=d.id);db.commit();return {'ok':True,'id':incident_id}

def event_out(e,db):
    c=db.get(Child,e.child_id); s=db.get(Staff,e.performed_by_id) if e.performed_by_id else None; r=db.get(Room,e.room_id) if e.room_id else None
    return {'id':e.id,'type':e.type,'effective_at':e.effective_at,'created_at':e.created_at,'data':clean_domain_data(e.data),'child':public_child(c),'room':r.name if r else None,'performed_by':((s.preferred_name or s.first_name)+' '+s.last_name[:1]+'.') if s else None,'revision':e.revision,'finalised':e.finalised,'visibility':e.visibility}

@app.get('/api/parent/me')
def parent_me(p:Parent=Depends(parent),db:Session=Depends(get_db)):
    centre=db.get(Centre,p.centre_id);zone=ZoneInfo(centre.timezone);today=now().astimezone(zone).date();children=[db.get(Child,x.child_id) for x in db.scalars(select(ParentChild).where(ParentChild.parent_id==p.id))];return {'children':[public_child(c) for c in children if c and c.active],'centre':centre.name,'centre_id':centre.id,'display_name':centre.display_name,'secondary_text':centre.secondary_text,'logo_url':f'/api/branding/{centre.id}/logo' if centre.logo_path else None,'timezone':centre.timezone,'today':today.isoformat(),'oldest_online_date':(today-timedelta(days=centre.parent_history_days-1)).isoformat()}
@app.get('/api/parent/children/{child_id}/timeline')
def timeline(child_id:str,day:str|None=None,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    accessible=db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==child_id))
    if not accessible:raise HTTPException(404,'Child not found')
    centre=db.get(Centre,p.centre_id); zone=ZoneInfo(centre.timezone); target=datetime.fromisoformat(day).date() if day else now().astimezone(zone).date()
    if target < now().astimezone(zone).date()-timedelta(days=centre.parent_history_days-1):raise HTTPException(403,'This date is outside the family history window')
    start=datetime.combine(target,datetime.min.time(),tzinfo=zone).astimezone(timezone.utc); end=datetime.combine(target+timedelta(days=1),datetime.min.time(),tzinfo=zone).astimezone(timezone.utc)
    q=select(Event).where(Event.centre_id==p.centre_id,Event.child_id==child_id,Event.visibility=='parent',Event.effective_at>=start,Event.effective_at<end).order_by(Event.effective_at)
    return [event_out(e,db) for e in db.scalars(q)]

@app.get('/api/parent/children/{child_id}/day')
def parent_day(child_id:str,day:date|None=None,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    accessible=db.scalar(
        select(ParentChild).where(
            ParentChild.parent_id==p.id,
            ParentChild.child_id==child_id
        )
    )
    if not accessible:
        raise HTTPException(404,'Child not found')

    centre=db.get(Centre,p.centre_id)
    zone=ZoneInfo(centre.timezone)

    target=(
        day
        if day
        else now().astimezone(zone).date()
    )

    today=now().astimezone(zone).date()
    oldest=today-timedelta(days=centre.parent_history_days-1)

    if target<oldest or target>today:
        raise HTTPException(
            403,
            'This date is outside the family history window'
        )

    start=datetime.combine(
        target,
        datetime.min.time(),
        tzinfo=zone
    ).astimezone(timezone.utc)

    end=datetime.combine(
        target+timedelta(days=1),
        datetime.min.time(),
        tzinfo=zone
    ).astimezone(timezone.utc)

    attendance=list(
        db.scalars(
            select(Attendance)
            .where(
                Attendance.centre_id==p.centre_id,
                Attendance.child_id==child_id,
                Attendance.arrived_at<end,
                or_(
                    Attendance.departed_at.is_(None),
                    Attendance.departed_at>=start
                )
            )
            .order_by(Attendance.arrived_at)
        )
    )

    sleeps=list(
        db.scalars(
            select(SleepSession)
            .where(
                SleepSession.centre_id==p.centre_id,
                SleepSession.child_id==child_id,
                SleepSession.put_down_at<end,
                or_(
                    SleepSession.got_up_at.is_(None),
                    SleepSession.got_up_at>=start
                )
            )
            .order_by(SleepSession.put_down_at)
        )
    )

    events=list(
        db.scalars(
            select(Event)
            .where(
                Event.centre_id==p.centre_id,
                Event.child_id==child_id,
                Event.visibility=='parent',
                Event.type!='sleep',
                Event.effective_at>=start,
                Event.effective_at<end
            )
            .order_by(Event.effective_at)
        )
    )

    attendance_out=[]

    for a in attendance:
        room=db.get(Room,a.room_id) if a.room_id else None
        attendance_out.append({
            'id':a.id,
            'arrived_at':a.arrived_at,
            'departed_at':a.departed_at,
            'room':room.name if room else None
        })

    sleep_out=[]

    for s in sleeps:
        room=db.get(Room,s.room_id) if s.room_id else None

        duration=None

        if s.fell_asleep_at and s.woke_at:
            seconds=(
                utc(s.woke_at)-utc(s.fell_asleep_at)
            ).total_seconds()

            if seconds>=0:
                duration=round(seconds/60)

        sleep_out.append({
            'id':s.id,
            'put_down_at':s.put_down_at,
            'fell_asleep_at':s.fell_asleep_at,
            'woke_at':s.woke_at,
            'got_up_at':s.got_up_at,
            'duration_minutes':duration,
            'quality':s.quality,
            'wake_state':s.wake_state,
            'note':s.note,
            'room':room.name if room else None
        })

    return {
        'date':target.isoformat(),
        'attendance':attendance_out,
        'sleep_sessions':sleep_out,
        'events':[event_out(e,db) for e in events]
    }

@app.post('/api/parent/notes')
def parent_note(body:NoteIn,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    if not db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==body.child_id)):raise HTTPException(404,'Child not found')
    n=ParentNote(centre_id=p.centre_id,child_id=body.child_id,body=body.body);db.add(n);db.commit();return {'id':n.id,'created_at':n.created_at}
@app.post('/api/parent/data-requests')
def create_data_request(body:DataRequestIn,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    if body.end_date<body.start_date:raise HTTPException(422,'End date must be on or after start date')
    if not db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==body.child_id)):raise HTTPException(404,'Child not found')
    existing=db.scalar(select(ParentDataRequest).where(ParentDataRequest.parent_id==p.id,ParentDataRequest.child_id==body.child_id,ParentDataRequest.start_date==body.start_date,ParentDataRequest.end_date==body.end_date,ParentDataRequest.status.in_(['new','in_progress'])))
    if existing:return {'id':existing.id,'status':existing.status,'idempotent':True}
    item=ParentDataRequest(centre_id=p.centre_id,parent_id=p.id,child_id=body.child_id,start_date=body.start_date,end_date=body.end_date,note=body.note,status='new');db.add(item);db.flush();audit(db,p.centre_id,'parent_data_request',item.id,'created',after={'child_id':body.child_id,'start_date':body.start_date.isoformat(),'end_date':body.end_date.isoformat()});db.commit();return {'id':item.id,'status':item.status}
@app.get('/api/parent/children/{child_id}/export')
def export(child_id:str,day:date|None=None,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    if not db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==child_id)):raise HTTPException(404,'Child not found')
    import csv,io
    record=parent_day(child_id,day,p,db);out=io.StringIO();w=csv.writer(out);w.writerow(['effective_time','type','summary','room','performed_by'])
    arrivals=sorted((x for x in record['attendance'] if x['arrived_at']),key=lambda x:x['arrived_at'])
    departures=sorted((x for x in record['attendance'] if x['departed_at']),key=lambda x:x['departed_at'])
    if arrivals:w.writerow([arrivals[0]['arrived_at'],'Drop off','Arrived at centre',arrivals[0]['room'],''])
    rows=[]
    for sleep in record['sleep_sessions']:
        moments=[f"put down {sleep['put_down_at']}" if sleep['put_down_at'] else None,f"fell asleep {sleep['fell_asleep_at']}" if sleep['fell_asleep_at'] else None,f"woke {sleep['woke_at']}" if sleep['woke_at'] else None,f"got up {sleep['got_up_at']}" if sleep['got_up_at'] else None]
        rows.append((sleep['put_down_at'] or sleep['fell_asleep_at'],'Sleep','; '.join(x for x in moments if x)+(f"; duration {sleep['duration_minutes']} min" if sleep['duration_minutes'] is not None else ''),sleep['room'],''))
    for event in record['events']:
        rows.append((event['effective_at'],event['type'].replace('_',' ').title(),' · '.join(f'{k}: {v}' for k,v in event['data'].items() if v not in (None,'',[])),event['room'],event['performed_by']))
    for row in sorted(rows,key=lambda x:x[0] or ''):w.writerow(row)
    if departures:w.writerow([departures[-1]['departed_at'],'Pick up','Departed centre',departures[-1]['room'],''])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="daily-record.csv"'})

@app.on_event('startup')
def seed():
    if APP_ENV=='production':
        known={'development-only-change-me','development-only-change-me-replace-before-production','replace-with-a-long-random-secret'}
        if SECRET in known or len(SECRET)<32: raise RuntimeError('Production requires a unique, non-example SECRET_KEY of at least 32 characters')
        if not secure_cookie: raise RuntimeError('Production requires COOKIE_SECURE=true')
        if os.getenv('DEMO_SEED','false').lower()=='true': raise RuntimeError('Production must not seed demo data')
        if 'change-me-before-production' in os.getenv('DATABASE_URL',''): raise RuntimeError('Production requires a non-example database password')
        if not os.getenv('PUBLIC_ORIGIN','').startswith('https://'): raise RuntimeError('Production requires an HTTPS PUBLIC_ORIGIN')
    if os.getenv('DEMO_SEED','false').lower()!='true':return
    from .db import SessionLocal
    db=SessionLocal()
    try:
        if db.scalar(select(Centre).limit(1)):return
        c=Centre(name='Kōwhai Grove Early Learning',branch='Demo Centre');db.add(c);db.flush()
        rooms=[Room(centre_id=c.id,name=n,accent=a,icon=i) for n,a,i in [('Kōwhai','#176b5b','🌿'),('Rimu','#426b9b','🌲'),('Pōhutukawa','#a64646','🌺'),('Harakeke','#80633d','🪴')]];db.add_all(rooms);db.flush()
        db.add(Account(centre_id=c.id,email='admin@demo.local',password_hash=pwd.hash('ChangeMe123!')))
        staff=[Staff(centre_id=c.id,first_name='Sarah',last_name='Taylor',pin_hash=pwd.hash('1234')),Staff(centre_id=c.id,first_name='Michael',last_name='Ngata',pin_hash=pwd.hash('2345')),Staff(centre_id=c.id,first_name='Aroha',last_name='Wilson',pin_hash=pwd.hash('3456'))];db.add_all(staff)
        names=['Mila Chen','Theo Banks','Isla Hart','Noah Bell','Ava Patel','Leo Wright','Ella Ross','Finn Lane','Ruby King','Arlo Webb','Zoe Gray','Jack Moon','Ivy Stone','Max Reed','Luna Fox','Owen Price','Mia Lake','Kai Birch','Eva North','Sam Coast']
        children=[Child(centre_id=c.id,room_id=rooms[i%4].id,first_name=n.split()[0],last_name=n.split()[1]) for i,n in enumerate(names)];db.add_all(children);db.flush()
        p=Parent(centre_id=c.id,name='Demo Family',login='demo-parent',pin_hash=pwd.hash('123456'));db.add(p);db.flush();db.add_all([ParentChild(parent_id=p.id,child_id=children[0].id),ParentChild(parent_id=p.id,child_id=children[1].id)])
        medicines=[MedicationAuthority(centre_id=c.id,child_id=children[0].id,medication_name='Demo inhaler',dose='2 puffs',route='inhaled',category='ii',status='authorised',signer_name='Demo Parent',scheduled_times=['12:00'],instructions='Use spacer and allow normal breathing.'),MedicationAuthority(centre_id=c.id,child_id=children[0].id,medication_name='Demo antihistamine',dose='5 mL',route='oral',category='ii',status='authorised',signer_name='Demo Parent',scheduled_times=[],instructions='As directed for the fictional trial.')];db.add_all(medicines);db.flush()
        for medicine in medicines:
            db.add(Signature(centre_id=c.id,parent_id=p.id,signer_name='Demo Parent',relationship='parent',domain_type='medication_authority',domain_id=medicine.id,revision=medicine.revision,purpose='medication authority',signature_data='demo-signature-not-for-production'))
            db.add(MedicationReceipt(centre_id=c.id,authority_id=medicine.id,received_by_id=staff[0].id,handed_by='Demo Parent',label_checked=True,authority_matched=True,expiry_checked=True,storage_location='Demo medicine cupboard',quantity='Trial quantity'))
        db.add(ParentNote(centre_id=c.id,child_id=children[0].id,body='Mila had a poor sleep last night and may be tired.'))
        db.commit()
    finally:db.close()
