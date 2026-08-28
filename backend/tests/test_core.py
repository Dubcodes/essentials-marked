import os
import hashlib
from datetime import timedelta
import pytest
os.environ['DATABASE_URL']='sqlite:///./test.db'
os.environ['DEMO_SEED']='false'
from fastapi.testclient import TestClient
import app.main as main_module
from app.main import app, pwd, enforce_failure_limit, record_auth_failure, verify_staff_pin
from app.db import Base, engine, SessionLocal
from app.models import Centre, Account, Room, Staff, Child, Parent, ParentChild, Attendance, Event, MedicationAuthority, MedicationAdministration, MedicationReceipt, Signature, SleepSession, SleepCheck, Incident, IncidentAction, IncidentBodyArea, LoginAttempt, AppSession, now

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

def test_ended_room_visit_is_cleared_and_stays_cleared_after_bootstrap():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        visiting=Room(centre_id=centre.id,name='Visiting Room');children[0].room_id=room.id;db.add(visiting);db.commit()
        client=TestClient(app);paired(client,room);child=children[0]
        assert client.post('/api/classroom/presence',json={'child_id':child.id,'room_id':room.id,'action':'arrive'}).status_code==200
        assert client.post('/api/classroom/presence',json={'child_id':child.id,'room_id':visiting.id,'action':'visit'}).status_code==200
        during=next(item for item in client.get('/api/classroom/bootstrap').json()['children'] if item['id']==child.id)
        assert during['present'] and during['visiting_room_id']==visiting.id
        ended=client.post('/api/classroom/presence',json={'child_id':child.id,'room_id':visiting.id,'action':'end_visit'})
        assert ended.status_code==200 and ended.json()['visiting_room_id'] is None
        attendance=db.query(Attendance).filter_by(child_id=child.id).one();db.refresh(attendance)
        assert attendance.visit_room_id is None and attendance.last_visit_room_id==visiting.id and attendance.visit_ended_at is not None
        refreshed=next(item for item in client.get('/api/classroom/bootstrap').json()['children'] if item['id']==child.id)
        assert refreshed['visiting_room_id'] is None and refreshed['room_id']==room.id and refreshed['present']
    finally:db.close()
def test_medication_pin_is_ephemeral():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        assert client.post('/api/medication/authorities',json={'child_id':children[0].id,'medication_name':'Bad date','dose':'5ml','route':'oral','category':'ii','starts_on':'not-a-date'}).status_code==422
        assert client.post('/api/medication/authorities',json={'child_id':children[0].id,'medication_name':'Bad range','dose':'5ml','route':'oral','category':'ii','starts_on':'2030-01-02','ends_on':'2030-01-01'}).status_code==422
        today=now().date();start=today-timedelta(days=1);end=today+timedelta(days=1)
        authority=client.post('/api/medication/authorities',json={'child_id':children[0].id,'medication_name':'Demo medicine','dose':'5ml','route':'oral','category':'ii','signer_name':'Forged Admin Signature','starts_on':start.isoformat(),'ends_on':end.isoformat()}).json()
        assert authority['status']=='draft'
        assert client.post('/api/medication/receipts',json={'authority_id':authority['id'],'staff_id':staff.id,'label_checked':True,'authority_matched':True,'expiry_checked':True}).status_code==409
        assert client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'}).status_code==200
        signed=client.post(f"/api/parent/medication-authorities/{authority['id']}/authorise",json={'signer_name':'Demo Parent','relationship':'parent','signature_data':'signature-data','purpose':'medication authority'})
        assert signed.status_code==200 and db.query(Signature).count()==1
        assert client.post('/api/medication/receipts',json={'authority_id':authority['id'],'staff_id':staff.id,'label_checked':True,'authority_matched':True,'expiry_checked':True}).status_code==200
        assert client.post('/api/medication/receipts',json={'authority_id':authority['id'],'staff_id':staff.id,'label_checked':True,'authority_matched':True,'expiry_checked':True}).status_code==409
        before=(start-timedelta(days=2)).isoformat()+'T12:00:00Z';after=(end+timedelta(days=2)).isoformat()+'T12:00:00Z'
        assert client.post('/api/classroom/medication/administrations',json={'client_operation_id':'medicine-date-before','authority_id':authority['id'],'room_id':room.id,'staff_id':staff.id,'staff_pin':'1234','outcome':'given','dose':'5ml','administered_at':before}).status_code==409
        assert client.post('/api/classroom/medication/administrations',json={'client_operation_id':'medicine-date-after1','authority_id':authority['id'],'room_id':room.id,'staff_id':staff.id,'staff_pin':'1234','outcome':'given','dose':'5ml','administered_at':after}).status_code==409
        bad=client.post('/api/classroom/medication/administrations',json={'client_operation_id':'medicine-op-bad-1','authority_id':authority['id'],'room_id':room.id,'staff_id':staff.id,'staff_pin':'0000','outcome':'given','dose':'5ml'});assert bad.status_code==403
        assert client.post('/api/classroom/medication/administrations',json={'client_operation_id':'medicine-dose-bad','authority_id':authority['id'],'room_id':room.id,'staff_id':staff.id,'staff_pin':'1234','outcome':'given','dose':'6ml'}).status_code==409
        payload={'client_operation_id':'medicine-op-good-1','authority_id':authority['id'],'room_id':room.id,'staff_id':staff.id,'staff_pin':'1234','outcome':'given','dose':'5 ml'}
        ok=client.post('/api/classroom/medication/administrations',json=payload);assert ok.status_code==200 and '1234' not in ok.text
        retry=client.post('/api/classroom/medication/administrations',json=payload);assert retry.status_code==200 and retry.json()['idempotent']
        assert client.post('/api/classroom/medication/administrations',json={**payload,'note':'changed replay'}).status_code==409
        assert db.query(MedicationAdministration).count()==1 and db.query(Event).filter(Event.type=='medicine').count()==1
        assert '1234' not in str([x.data for x in db.query(Event).all()])
        receipt=db.query(MedicationReceipt).filter_by(authority_id=authority['id']).one()
        returned=client.post(f'/api/medication/receipts/{receipt.id}/return',json={'staff_id':staff.id,'returned_to':'Demo parent'})
        db.expire_all()
        assert returned.status_code==200 and db.get(MedicationReceipt,receipt.id).returned_at is not None
        assert client.post('/api/classroom/medication/administrations',json={**payload,'client_operation_id':'medicine-returned-1'}).status_code==409
    finally: db.close()
def test_current_medicine_categories_and_sleep_timer_states():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        # Category iii is not accepted for this centre-based workflow.
        assert client.post('/api/medication/authorities',json={'child_id':children[0].id,'medication_name':'Demo','dose':'1ml','route':'oral','category':'iii'}).status_code==422
        settling=client.post('/api/classroom/sleep',json={'client_id':'sleep-put-down-1','child_ids':[children[0].id],'room_id':room.id,'action':'put_down','staff_id':staff.id});assert settling.status_code==200
        # A settling child is not marked overdue before falling asleep.
        assert client.get('/api/classroom/sleep-status').json()['status']=='green'
        assert client.post('/api/classroom/sleep',json={'client_id':'sleep-asleep-1','child_ids':[children[0].id],'room_id':room.id,'action':'fell_asleep','staff_id':staff.id}).status_code==200
        assert client.post('/api/classroom/sleep',json={'client_id':'sleep-wake-1','child_ids':[children[0].id],'room_id':room.id,'action':'wake','staff_id':staff.id}).status_code==200
        assert client.get('/api/classroom/sleep-status').json()['status']=='green'
        assert client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'}).status_code==200
        timeline=client.get(f'/api/parent/children/{children[0].id}/timeline').json()
        assert [item['data']['state'] for item in timeline]==['put down','fell asleep','wake']
        assert timeline[-1]['data']['duration_minutes'] is not None and all(item['data']['state']!='check' for item in timeline)
    finally: db.close()

def test_sleep_state_guards_room_binding_and_bulk_idempotency():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        alternate=Room(centre_id=centre.id,name='R2');db.add(alternate);db.commit()
        client=TestClient(app);paired(client,room)
        base={'child_ids':[c.id for c in children],'room_id':room.id,'staff_id':staff.id}
        assert client.post('/api/classroom/sleep',json={**base,'client_id':'sleep-check-too-early','action':'check'}).status_code==409
        put={**base,'client_id':'sleep-bulk-put-001','action':'put_down'}
        assert client.post('/api/classroom/sleep',json=put).status_code==200
        assert client.post('/api/classroom/sleep',json=put).json()['idempotent']
        assert db.query(SleepSession).count()==2
        assert client.post('/api/classroom/sleep',json={**base,'client_id':'sleep-wake-too-early','action':'wake'}).status_code==409
        assert client.post('/api/classroom/sleep',json={**base,'client_id':'sleep-bulk-asleep1','action':'fell_asleep'}).status_code==200
        assert client.post('/api/classroom/sleep',json={**base,'room_id':alternate.id,'client_id':'sleep-wrong-room-1','action':'check'}).status_code==409
        check={**base,'client_id':'sleep-bulk-check-01','action':'check'}
        assert client.post('/api/classroom/sleep',json=check).status_code==200
        assert client.post('/api/classroom/sleep',json=check).json()['idempotent']
        assert client.post('/api/classroom/sleep',json={**check,'note':'changed replay'}).status_code==409
        assert db.query(SleepCheck).count()==2
        assert client.post('/api/classroom/sleep',json={**base,'client_id':'sleep-bulk-wake-01','action':'wake'}).status_code==200
        assert client.post('/api/classroom/sleep',json={**base,'client_id':'sleep-check-after-wake','action':'check'}).status_code==409
        assert client.post('/api/classroom/sleep',json={**base,'client_id':'sleep-bulk-gotup01','action':'got_up'}).status_code==200
        assert client.get('/api/classroom/sleep-status').json()['active']==0
    finally: db.close()

def test_incident_draft_finalise_idempotency_and_parent_privacy():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        base={'client_draft_id':'incident-draft-0001','child_id':children[0].id,'other_child_id':children[1].id,'room_id':room.id,'staff_id':staff.id,'incident_type':'bump','body_areas':['head'],'actions':['cold pack']}
        invalid=client.post('/api/classroom/incidents',json={**base,'client_draft_id':'incident-invalid-01','body_areas':['not-a-body-area']});assert invalid.status_code==422
        draft=client.post('/api/classroom/incidents',json=base);assert draft.status_code==200 and draft.json()['status']=='draft'
        incident_id=draft.json()['id'];updated={**base,'incident_id':incident_id,'description':'Minor bump'}
        assert client.post('/api/classroom/incidents',json=updated).status_code==200
        assert db.query(Incident).count()==1 and db.query(IncidentAction).count()==1 and db.query(IncidentBodyArea).count()==1
        final={**updated,'finalise':True,'finalise_operation_id':'incident-final-0001','staff_pin':'1234'}
        result=client.post('/api/classroom/incidents',json=final);assert result.status_code==200 and result.json()['status']=='finalised'
        retry=client.post('/api/classroom/incidents',json=final);assert retry.status_code==200 and retry.json()['idempotent']
        assert client.post('/api/classroom/incidents',json={**final,'description':'Changed after finalisation'}).status_code==409
        assert client.post('/api/classroom/incidents',json={**final,'finalise_operation_id':'incident-final-0002'}).status_code==409
        assert db.query(Event).filter(Event.type=='incident').count()==1 and db.query(IncidentAction).count()==1 and db.query(IncidentBodyArea).count()==1
        assert client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'}).status_code==200
        parent_event=client.get(f'/api/parent/children/{children[0].id}/timeline').json()[0];wire=str(parent_event)
        assert children[1].id not in wire and children[1].first_name not in wire and 'another child' in wire
        assert parent_event['data']['body_areas']==['head'] and parent_event['data']['actions']==['cold pack']
    finally: db.close()

def test_server_session_sliding_expiry_revocation_and_rate_window():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app)
        assert client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        session=db.query(AppSession).filter_by(subject_type='admin').one();session.expires_at=now()+timedelta(minutes=1);db.commit();before=session.expires_at
        assert client.get('/api/admin/bootstrap').status_code==200
        db.refresh(session);assert session.expires_at>before
        session.revoked_at=now();db.commit();assert client.get('/api/admin/bootstrap').status_code==401
        for _ in range(8):record_auth_failure(db,'focused-test','same-key')
        with pytest.raises(Exception) as blocked:
            enforce_failure_limit(db,'focused-test','same-key')
        assert getattr(blocked.value,'status_code',None)==429
        for attempt in db.query(LoginAttempt).filter_by(scope='focused-test',key='same-key'):attempt.window_start=now()-timedelta(minutes=11)
        db.commit();enforce_failure_limit(db,'focused-test','same-key')
    finally: db.close()

def test_failed_pin_budget_ignores_success_and_resets_safely():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        for _ in range(3):
            with pytest.raises(Exception) as denied:verify_staff_pin(db,staff,'0000','bad pin')
            assert getattr(denied.value,'status_code',None)==403
        verify_staff_pin(db,staff,'1234','bad pin')
        assert db.query(LoginAttempt).filter_by(scope='staff_pin',key=staff.id).count()==0
        for _ in range(12):verify_staff_pin(db,staff,'1234','bad pin')
        for _ in range(8):
            with pytest.raises(Exception):verify_staff_pin(db,staff,'0000','bad pin')
        with pytest.raises(Exception) as blocked:verify_staff_pin(db,staff,'1234','bad pin')
        assert getattr(blocked.value,'status_code',None)==429
        for index,attempt in enumerate(db.query(LoginAttempt).filter_by(scope='staff_pin',key=staff.id)):attempt.window_start=now()-timedelta(minutes=11+index)
        db.commit();verify_staff_pin(db,staff,'1234','bad pin')
    finally:db.close()

def test_successful_admin_parent_and_pairing_auth_clear_failures():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app)
        for _ in range(2):assert client.post('/api/auth/admin/login',json={'email':'a@test','password':'wrong'}).status_code==401
        assert client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        assert db.query(LoginAttempt).filter_by(scope='admin',key='a@test').count()==0
        for _ in range(2):assert client.post('/api/auth/parent/login',json={'login':'p','pin':'000000'}).status_code==401
        assert client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'}).status_code==200
        assert db.query(LoginAttempt).filter_by(scope='parent',key='p').count()==0
        pairing=client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Rate-test tablet'}).json()
        for _ in range(2):assert client.post('/api/device/pair',json={'token':pairing['token'],'challenge':'000'}).status_code==400
        assert client.post('/api/device/pair',json={'token':pairing['token'],'challenge':pairing['challenge']}).status_code==200
        key=hashlib.sha256(pairing['token'].encode()).hexdigest();assert db.query(LoginAttempt).filter_by(scope='pairing',key=key).count()==0
    finally:db.close()

def test_production_startup_guard_rejects_defaults(monkeypatch):
    monkeypatch.setattr(main_module,'APP_ENV','production');monkeypatch.setattr(main_module,'SECRET','development-only-change-me');monkeypatch.setattr(main_module,'secure_cookie',False)
    with pytest.raises(RuntimeError):main_module.seed()
    monkeypatch.setattr(main_module,'SECRET','x'*40);monkeypatch.setattr(main_module,'secure_cookie',True)
    monkeypatch.setenv('DEMO_SEED','false');monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://user:unique@db/app');monkeypatch.setenv('PUBLIC_ORIGIN','https://example.test')
    assert main_module.seed() is None
