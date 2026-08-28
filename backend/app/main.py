import os, secrets, hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal
import jwt
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import get_db
from .models import Centre, Room, Staff, Account, Child, Parent, ParentChild, Event, Attendance, Device, Pairing, Audit, ParentNote, now

app = FastAPI(title='Essentials Marked', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173').split(','), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
# bcrypt is an adaptive, salted password hash supported in constrained local
# environments. The image also includes Argon2 for future migration support.
pwd = CryptContext(schemes=['bcrypt'], deprecated='auto')
SECRET = os.getenv('SECRET_KEY','development-only-change-me')
secure_cookie = os.getenv('COOKIE_SECURE','false').lower() == 'true'
RATE: dict[str, list[datetime]] = {}

def token(data, minutes=10080): return jwt.encode({**data, 'exp': datetime.now(timezone.utc)+timedelta(minutes=minutes)}, SECRET, algorithm='HS256')
def claim(request: Request, kind: str):
    raw = request.cookies.get(kind)
    if not raw: raise HTTPException(401, 'Sign in required')
    try:
        data = jwt.decode(raw, SECRET, algorithms=['HS256'])
        if data.get('kind') != kind: raise ValueError()
        return data
    except Exception: raise HTTPException(401, 'Session expired')
def admin(request: Request, db: Session=Depends(get_db)):
    data=claim(request,'admin'); a=db.get(Account,data['id'])
    if not a or not a.active: raise HTTPException(401,'Session revoked')
    return a
def parent(request: Request, db: Session=Depends(get_db)):
    data=claim(request,'parent'); p=db.get(Parent,data['id'])
    if not p or not p.active: raise HTTPException(401,'Session revoked')
    return p
def device(request: Request, db: Session=Depends(get_db)):
    data=claim(request,'device'); d=db.get(Device,data['id'])
    if not d or d.revoked: raise HTTPException(401,'Device session revoked')
    d.last_active_at=now(); db.commit(); return d
def scoped(db, cls, centre_id): return db.scalars(select(cls).where(cls.centre_id==centre_id))
def rate(key):
    attempts=RATE.setdefault(key,[]); cutoff=now()-timedelta(minutes=10); attempts[:]=[x for x in attempts if x>cutoff]
    if len(attempts)>=8: raise HTTPException(429,'Too many attempts; try later')
    attempts.append(now())
def audit(db, centre, entity, entity_id, action, before=None, after=None, actor=None, reason=None): db.add(Audit(centre_id=centre,entity=entity,entity_id=entity_id,action=action,before=before,after=after,actor_id=actor,reason=reason))
def public_child(c): return {'id':c.id,'first_name':c.preferred_name or c.first_name,'last_name':c.last_name,'room_id':c.room_id}

class Login(BaseModel): email: str; password: str
class ParentLogin(BaseModel): login: str; pin: str = Field(pattern=r'^\d{6}$')
class EventIn(BaseModel): client_id: str = Field(min_length=10,max_length=80); child_ids: list[str] = Field(min_length=1,max_length=50); type: Literal['nappy','toilet','food','sleep_start','sleep_end','sleep_check','sunscreen','medicine','incident','staff_note','supply']; effective_at: datetime | None=None; performed_by_id: str | None=None; data: dict = Field(default_factory=dict); staff_pin: str | None=None
class PairIn(BaseModel): room_id: str | None=None; label: str=Field(min_length=2,max_length=120)
class PairComplete(BaseModel): token: str; challenge: str
class Correction(BaseModel): performed_by_id: str; reason: str=Field(min_length=3,max_length=500)
class PresenceIn(BaseModel): child_id: str; action: Literal['arrive','depart','visit','end_visit']
class NoteIn(BaseModel): child_id: str; body: str=Field(min_length=1,max_length=1500)
class RoomIn(BaseModel): name: str=Field(min_length=2,max_length=100); accent: str='#176b5b'; icon: str='🌿'

@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/auth/admin/login')
def admin_login(body: Login, response: Response, request: Request, db: Session=Depends(get_db)):
    rate('admin:'+request.client.host); a=db.scalar(select(Account).where(Account.email==body.email.lower()))
    if not a or not pwd.verify(body.password,a.password_hash): raise HTTPException(401,'Invalid credentials')
    response.set_cookie('admin',token({'id':a.id,'centre_id':a.centre_id,'kind':'admin'}),httponly=True,samesite='lax',secure=secure_cookie,max_age=604800)
    return {'centre_id':a.centre_id,'role':a.role}
@app.post('/api/auth/parent/login')
def parent_login(body: ParentLogin,response: Response,request:Request,db:Session=Depends(get_db)):
    rate('parent:'+request.client.host); p=db.scalar(select(Parent).where(Parent.login==body.login.lower()))
    if not p or not pwd.verify(body.pin,p.pin_hash): raise HTTPException(401,'Invalid login or PIN')
    response.set_cookie('parent',token({'id':p.id,'centre_id':p.centre_id,'kind':'parent'}),httponly=True,samesite='lax',secure=secure_cookie,max_age=2592000)
    return {'ok':True}
@app.post('/api/auth/logout')
def logout(response:Response):
    for k in ('admin','parent','device'): response.delete_cookie(k)
    return {'ok':True}

@app.get('/api/admin/bootstrap')
def bootstrap(a:Account=Depends(admin),db:Session=Depends(get_db)):
    c=db.get(Centre,a.centre_id)
    return {'centre': {'id':c.id,'name':c.name,'branch':c.branch,'parent_history_days':c.parent_history_days}, 'rooms':[{'id':x.id,'name':x.name,'accent':x.accent,'icon':x.icon} for x in scoped(db,Room,a.centre_id)], 'staff':[{'id':x.id,'name':(x.preferred_name or x.first_name)+' '+x.last_name[:1]+'.','active':x.active} for x in scoped(db,Staff,a.centre_id)], 'children':[public_child(x) for x in scoped(db,Child,a.centre_id)], 'devices':[{'id':x.id,'label':x.label,'default_room_id':x.default_room_id,'last_active_at':x.last_active_at,'revoked':x.revoked} for x in scoped(db,Device,a.centre_id)]}
@app.post('/api/admin/rooms')
def create_room(body:RoomIn,a:Account=Depends(admin),db:Session=Depends(get_db)):
    r=Room(centre_id=a.centre_id,**body.model_dump());db.add(r);db.commit();return {'id':r.id,'name':r.name,'accent':r.accent,'icon':r.icon}
@app.post('/api/admin/pairings')
def create_pairing(body:PairIn,a:Account=Depends(admin),db:Session=Depends(get_db)):
    if body.room_id and not db.scalar(select(Room).where(Room.id==body.room_id,Room.centre_id==a.centre_id)): raise HTTPException(404,'Room not found')
    raw=secrets.token_urlsafe(32); challenge=str(secrets.randbelow(900)+100); p=Pairing(centre_id=a.centre_id,room_id=body.room_id,token_hash=hashlib.sha256(raw.encode()).hexdigest(),challenge=challenge,expires_at=now()+timedelta(seconds=60));db.add(p);db.commit();return {'token':raw,'challenge':challenge,'expires_at':p.expires_at,'label':body.label}
@app.get('/api/admin/events')
def events(day:str|None=None,room_id:str|None=None,staff_id:str|None=None,a:Account=Depends(admin),db:Session=Depends(get_db)):
    q=select(Event).where(Event.centre_id==a.centre_id)
    if room_id:q=q.where(Event.room_id==room_id)
    if staff_id:q=q.where(Event.performed_by_id==staff_id)
    if day:q=q.where(func.date(Event.effective_at)==day)
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

@app.post('/api/device/pair')
def pair(body:PairComplete,response:Response,db:Session=Depends(get_db)):
    p=db.scalar(select(Pairing).where(Pairing.token_hash==hashlib.sha256(body.token.encode()).hexdigest()))
    expiry = p.expires_at.replace(tzinfo=timezone.utc) if p and p.expires_at.tzinfo is None else (p.expires_at if p else now())
    if not p or p.consumed_at or expiry<now() or not secrets.compare_digest(p.challenge,body.challenge): raise HTTPException(400,'Pairing code invalid or expired')
    d=Device(centre_id=p.centre_id,label='Classroom tablet',default_room_id=p.room_id);p.consumed_at=now();db.add(d);db.commit();response.set_cookie('device',token({'id':d.id,'centre_id':d.centre_id,'kind':'device'}),httponly=True,samesite='lax',secure=secure_cookie,max_age=604800);return {'id':d.id,'room_id':d.default_room_id}
@app.get('/api/classroom/bootstrap')
def classroom_bootstrap(d:Device=Depends(device),db:Session=Depends(get_db)):
    children=list(scoped(db,Child,d.centre_id)); active_att={x.child_id:x for x in db.scalars(select(Attendance).where(Attendance.centre_id==d.centre_id,Attendance.arrived_at.is_not(None),Attendance.departed_at.is_(None)))}
    return {'device_id':d.id,'default_room_id':d.default_room_id,'rooms':[{'id':r.id,'name':r.name,'accent':r.accent,'icon':r.icon} for r in scoped(db,Room,d.centre_id)],'staff':[{'id':s.id,'name':(s.preferred_name or s.first_name)+' '+s.last_name[:1]+'.'} for s in scoped(db,Staff,d.centre_id) if s.active],'children':[public_child(c)|{'present':c.id in active_att,'visiting_room_id':active_att[c.id].visit_room_id if c.id in active_att else None} for c in children],'unread_notes':db.scalar(select(func.count()).select_from(ParentNote).where(ParentNote.centre_id==d.centre_id,ParentNote.read_at.is_(None)))}
@app.post('/api/classroom/presence')
def presence(body:PresenceIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    c=db.scalar(select(Child).where(Child.id==body.child_id,Child.centre_id==d.centre_id));
    if not c:raise HTTPException(404,'Child not found')
    a=db.scalar(select(Attendance).where(Attendance.child_id==c.id,Attendance.departed_at.is_(None)).order_by(Attendance.arrived_at.desc()))
    if body.action=='arrive':
        if not a:a=Attendance(centre_id=d.centre_id,child_id=c.id,room_id=c.room_id,arrived_at=now());db.add(a)
    elif not a: raise HTTPException(409,'Child is not present')
    elif body.action=='depart':a.departed_at=now();a.visit_ended_at=now() if a.visit_room_id else None
    elif body.action=='visit':a.visit_room_id=d.default_room_id;a.visit_started_at=now();a.visit_ended_at=None
    else:a.visit_ended_at=now()
    db.commit();return {'ok':True}
@app.post('/api/classroom/events')
def create_event(body:EventIn,d:Device=Depends(device),db:Session=Depends(get_db)):
    staff=db.get(Staff,body.performed_by_id) if body.performed_by_id else None
    if not staff or staff.centre_id!=d.centre_id:raise HTTPException(422,'Select a valid staff member')
    if body.type in ('medicine','incident'):
        if not body.staff_pin or not staff.pin_hash or not pwd.verify(body.staff_pin,staff.pin_hash):raise HTTPException(403,'Selected staff PIN is required')
    existing=db.scalar(select(Event).where(Event.centre_id==d.centre_id,Event.client_id==body.client_id))
    if existing:return {'events':[event_out(existing,db)],'idempotent':True}
    children=list(db.scalars(select(Child).where(Child.id.in_(body.child_ids),Child.centre_id==d.centre_id)))
    if len(children)!=len(set(body.child_ids)):raise HTTPException(404,'One or more children not found')
    items=[]
    for c in children:
        e=Event(centre_id=d.centre_id,room_id=d.default_room_id,child_id=c.id,type=body.type,effective_at=body.effective_at or now(),performed_by_id=staff.id,recorded_by_id=staff.id,device_id=d.id,client_id=body.client_id if c is children[0] else body.client_id+'-'+c.id,data=body.data,finalised=body.type in ('medicine','incident'));db.add(e);items.append(e)
    try:db.commit()
    except Exception:
        db.rollback(); existing=db.scalar(select(Event).where(Event.centre_id==d.centre_id,Event.client_id==body.client_id));
        if existing:return {'events':[event_out(existing,db)],'idempotent':True}
        raise
    return {'events':[event_out(e,db) for e in items],'idempotent':False}

def event_out(e,db):
    c=db.get(Child,e.child_id); s=db.get(Staff,e.performed_by_id) if e.performed_by_id else None; r=db.get(Room,e.room_id) if e.room_id else None
    return {'id':e.id,'type':e.type,'effective_at':e.effective_at,'created_at':e.created_at,'data':e.data,'child':public_child(c),'room':r.name if r else None,'performed_by':((s.preferred_name or s.first_name)+' '+s.last_name[:1]+'.') if s else None,'revision':e.revision,'finalised':e.finalised}

@app.get('/api/parent/me')
def parent_me(p:Parent=Depends(parent),db:Session=Depends(get_db)):
    children=[db.get(Child,x.child_id) for x in db.scalars(select(ParentChild).where(ParentChild.parent_id==p.id))];return {'children':[public_child(c) for c in children if c and c.active],'centre':db.get(Centre,p.centre_id).name}
@app.get('/api/parent/children/{child_id}/timeline')
def timeline(child_id:str,day:str|None=None,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    accessible=db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==child_id))
    if not accessible:raise HTTPException(404,'Child not found')
    centre=db.get(Centre,p.centre_id); target=datetime.fromisoformat(day).date() if day else now().date()
    if target < now().date()-timedelta(days=centre.parent_history_days-1):raise HTTPException(403,'This date is outside the family history window')
    q=select(Event).where(Event.centre_id==p.centre_id,Event.child_id==child_id,func.date(Event.effective_at)==target).order_by(Event.effective_at)
    return [event_out(e,db) for e in db.scalars(q)]
@app.post('/api/parent/notes')
def parent_note(body:NoteIn,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    if not db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==body.child_id)):raise HTTPException(404,'Child not found')
    n=ParentNote(centre_id=p.centre_id,child_id=body.child_id,body=body.body);db.add(n);db.commit();return {'id':n.id,'created_at':n.created_at}
@app.get('/api/parent/children/{child_id}/export')
def export(child_id:str,p:Parent=Depends(parent),db:Session=Depends(get_db)):
    if not db.scalar(select(ParentChild).where(ParentChild.parent_id==p.id,ParentChild.child_id==child_id)):raise HTTPException(404,'Child not found')
    import csv,io
    out=io.StringIO();w=csv.writer(out);w.writerow(['effective_time','type','summary','room','performed_by'])
    for e in db.scalars(select(Event).where(Event.centre_id==p.centre_id,Event.child_id==child_id).order_by(Event.effective_at)): o=event_out(e,db);w.writerow([o['effective_at'],o['type'],str(o['data']),o['room'],o['performed_by']])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="daily-record.csv"'})

@app.on_event('startup')
def seed():
    if os.getenv('DEMO_SEED','true').lower()!='true':return
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
        db.add(ParentNote(centre_id=c.id,child_id=children[0].id,body='Mila had a poor sleep last night and may be tired.'))
        db.commit()
    finally:db.close()
