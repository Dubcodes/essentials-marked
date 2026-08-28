import os
os.environ['DATABASE_URL']='sqlite:///./test.db'
os.environ['DEMO_SEED']='false'
from fastapi.testclient import TestClient
from app.main import app, pwd
from app.db import Base, engine, SessionLocal
from app.models import Centre, Account, Room, Staff, Child, Parent, ParentChild, Event

def setup():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);db=SessionLocal()
    centre=Centre(name='A');other=Centre(name='B');db.add_all([centre,other]);db.flush()
    account=Account(centre_id=centre.id,email='a@test',password_hash=pwd.hash('secret'));room=Room(centre_id=centre.id,name='R');other_room=Room(centre_id=other.id,name='Other');staff=Staff(centre_id=centre.id,first_name='S',last_name='T',pin_hash=pwd.hash('1234'));children=[Child(centre_id=centre.id,room_id=room.id,first_name='Child'),Child(centre_id=centre.id,room_id=room.id,first_name='Two')];parent=Parent(centre_id=centre.id,name='P',login='p',pin_hash=pwd.hash('123456'))
    db.add_all([account,room,other_room,staff,*children,parent]);db.flush();db.add(ParentChild(parent_id=parent.id,child_id=children[0].id));db.commit();return db,centre,account,room,other_room,staff,children,parent
def paired(client,room):
    assert client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
    pair=client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Tablet'}).json()
    assert client.post('/api/device/pair',json={'token':pair['token'],'challenge':pair['challenge']}).status_code==200
def test_parent_isolation_and_staff_notes_hidden():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        visible={'client_id':'visible-op-123','child_ids':[children[0].id],'type':'nappy','room_id':room.id,'performed_by_id':staff.id,'data':{'outcome':'Wet','staff_pin':'1234'}}
        hidden={'client_id':'private-op-123','child_ids':[children[0].id],'type':'staff_note','room_id':room.id,'performed_by_id':staff.id,'data':{'note':'internal','pin':'1234'}}
        assert client.post('/api/classroom/events',json=visible).status_code==200
        assert client.post('/api/classroom/events',json=hidden).status_code==200
        client.post('/api/auth/logout');assert client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'}).status_code==200
        timeline=client.get(f'/api/parent/children/{children[0].id}/timeline').json();wire=str(timeline)
        assert len(timeline)==1 and timeline[0]['type']=='nappy' and '1234' not in wire and 'internal' not in wire
        csv=client.get(f'/api/parent/children/{children[0].id}/export').text;assert '1234' not in csv and 'internal' not in csv
        assert client.get('/api/parent/children/not-linked/timeline').status_code==404
    finally: db.close()
def test_room_validation_bulk_retry_and_pin_never_persisted():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        payload={'client_id':'bulk-op-12345','child_ids':[c.id for c in children],'type':'sunscreen','room_id':room.id,'performed_by_id':staff.id,'data':{'application':'exposed skin','staff_pin':'1234'}}
        first=client.post('/api/classroom/events',json=payload);assert first.status_code==200 and len(first.json()['events'])==2
        retry=client.post('/api/classroom/events',json=payload);assert retry.status_code==200 and retry.json()['idempotent'] and len(retry.json()['events'])==2
        assert db.query(Event).count()==2
        assert '1234' not in str([x.data for x in db.query(Event).all()])
        payload['client_id']='cross-centre-123';payload['room_id']=other_room.id;assert client.post('/api/classroom/events',json=payload).status_code==404
    finally: db.close()
def test_medication_pin_is_ephemeral():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        authority=client.post('/api/medication/authorities',json={'child_id':children[0].id,'medication_name':'Demo medicine','dose':'5ml','route':'oral','category':'ii','signer_name':'Demo Parent'}).json()
        assert client.post('/api/medication/receipts',json={'authority_id':authority['id'],'staff_id':staff.id,'label_checked':True,'authority_matched':True,'expiry_checked':True}).status_code==200
        bad=client.post('/api/classroom/medication/administrations',json={'authority_id':authority['id'],'room_id':room.id,'staff_id':staff.id,'staff_pin':'0000','outcome':'given','dose':'5ml'});assert bad.status_code==403
        ok=client.post('/api/classroom/medication/administrations',json={'authority_id':authority['id'],'room_id':room.id,'staff_id':staff.id,'staff_pin':'1234','outcome':'given','dose':'5ml'});assert ok.status_code==200 and '1234' not in ok.text
        assert '1234' not in str([x.data for x in db.query(Event).all()])
    finally: db.close()
