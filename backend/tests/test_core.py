import os
os.environ['DATABASE_URL']='sqlite:///./test.db'
os.environ['DEMO_SEED']='false'
from fastapi.testclient import TestClient
from app.main import app, pwd
from app.db import Base, engine, SessionLocal
from app.models import Centre, Account, Room, Staff, Child, Parent, ParentChild

def setup():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);db=SessionLocal();c=Centre(name='A');other=Centre(name='B');db.add_all([c,other]);db.flush();a=Account(centre_id=c.id,email='a@test',password_hash=pwd.hash('secret'));r=Room(centre_id=c.id,name='R');s=Staff(centre_id=c.id,first_name='S',last_name='T',pin_hash=pwd.hash('1234'));ch=Child(centre_id=c.id,room_id=r.id,first_name='Child');p=Parent(centre_id=c.id,name='P',login='p',pin_hash=pwd.hash('123456'));db.add_all([a,r,s,ch,p]);db.flush();db.add(ParentChild(parent_id=p.id,child_id=ch.id));db.commit();return db,c,a,r,s,ch,p
def test_parent_cannot_access_other_child():
    db,c,a,r,s,ch,p=setup()
    try:
        client=TestClient(app);client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'});assert client.get('/api/parent/children/not-their-child/timeline').status_code==404
    finally: db.close()
def test_event_requires_pin_and_is_idempotent():
    db,c,a,r,s,ch,p=setup()
    try:
        client=TestClient(app)
        # Admin-authenticated setup gets pairing
        logged=client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'});assert logged.status_code==200, logged.text
        paired=client.post('/api/admin/pairings',json={'room_id':r.id,'label':'Tablet'});assert paired.status_code==200, paired.text
        pair=paired.json();client.post('/api/device/pair',json={'token':pair['token'],'challenge':pair['challenge']})
        base={'client_id':'x'*12,'child_ids':[ch.id],'type':'medicine','performed_by_id':s.id,'data':{}}
        assert client.post('/api/classroom/events',json=base).status_code==403
        base['staff_pin']='1234';assert client.post('/api/classroom/events',json=base).status_code==200;assert client.post('/api/classroom/events',json=base).json()['idempotent'] is True
    finally: db.close()
