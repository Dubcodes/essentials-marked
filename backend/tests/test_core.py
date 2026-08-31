import os
import hashlib
import io
from datetime import timedelta,datetime,timezone
import pytest
from sqlalchemy import select
os.environ['DATABASE_URL']='sqlite:///./test.db'
os.environ['DEMO_SEED']='false'
from fastapi.testclient import TestClient
import app.main as main_module
from app.main import app, pwd, enforce_failure_limit, record_auth_failure, verify_staff_pin
from app.db import Base, engine, SessionLocal
from app.models import Centre, Account, Room, Staff, Child, Parent, ParentChild, Attendance, RoomVisit, Audit, Event, MedicationAuthority, MedicationAdministration, MedicationReceipt, Signature, SleepSession, SleepCheck, Incident, IncidentAction, IncidentBodyArea, LoginAttempt, AppSession, now

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
        assert client.delete(f'/api/classroom/incidents/drafts/{incident_id}').status_code==409
        retry=client.post('/api/classroom/incidents',json=final);assert retry.status_code==200 and retry.json()['idempotent']
        assert client.post('/api/classroom/incidents',json={**final,'description':'Changed after finalisation'}).status_code==409
        assert client.post('/api/classroom/incidents',json={**final,'finalise_operation_id':'incident-final-0002'}).status_code==409
        assert db.query(Event).filter(Event.type=='incident').count()==1 and db.query(IncidentAction).count()==1 and db.query(IncidentBodyArea).count()==1
        assert client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'}).status_code==200
        parent_event=client.get(f'/api/parent/children/{children[0].id}/timeline').json()[0];wire=str(parent_event)
        assert children[1].id not in wire and children[1].first_name not in wire and 'another child' in wire
        assert parent_event['data']['body_areas']==['head'] and parent_event['data']['actions'][0]['description']=='cold pack'
        assert parent_event['data']['actions'][0]['action_at']
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

def test_ordinary_replay_requires_identical_material_request():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        payload={'client_id':'ordinary-fingerprint-001','child_ids':[children[0].id],'type':'nappy','room_id':room.id,'performed_by_id':staff.id,'data':{'outcome':'Wet'}}
        first=client.post('/api/classroom/events',json=payload);assert first.status_code==200
        assert client.post('/api/classroom/events',json=payload).json()['idempotent']
        assert client.post('/api/classroom/events',json={**payload,'data':{'outcome':'Dry'}}).status_code==409
        assert db.query(Event).filter_by(type='nappy').count()==1
    finally:db.close()

def test_food_batch_is_atomic_and_fingerprint_idempotent():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room)
        payload={'client_operation_id':'food-batch-fingerprint-01','room_id':room.id,'staff_id':staff.id,'meal':'lunch','description':None,'rows':[{'child_id':children[0].id,'food':'Pasta','servings':[1],'total_servings':1},{'child_id':children[1].id,'food':'Pasta','servings':[.5,.25],'total_servings':.75}]}
        first=client.post('/api/classroom/food-batch',json=payload);assert first.status_code==200 and len(first.json()['events'])==2
        assert client.post('/api/classroom/food-batch',json=payload).json()['idempotent']
        assert client.post('/api/classroom/food-batch',json={**payload,'rows':[payload['rows'][0],{**payload['rows'][1],'servings':[1]}]}).status_code==409
        invalid={**payload,'client_operation_id':'food-batch-invalid-0001','rows':[payload['rows'][0],{'child_id':'missing-child','total_servings':1}]}
        assert client.post('/api/classroom/food-batch',json=invalid).status_code==404
        assert db.query(Event).filter_by(type='food').count()==2
    finally:db.close()

def test_incident_draft_discard_removes_children_and_audits():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room);payload={'client_draft_id':'discard-draft-00001','child_id':children[0].id,'room_id':room.id,'staff_id':staff.id,'incident_type':'graze','body_areas':['left_hand'],'actions':[{'description':'washed','action_at':now().isoformat()}]}
        created=client.post('/api/classroom/incidents',json=payload);assert created.status_code==200;incident_id=created.json()['id']
        deleted=client.delete(f'/api/classroom/incidents/drafts/{incident_id}');assert deleted.status_code==200
        assert db.query(Incident).count()==0 and db.query(IncidentAction).count()==0 and db.query(IncidentBodyArea).count()==0
        audit_row=db.query(Audit).filter_by(entity='incident',entity_id=incident_id,action='draft_discarded').one();assert audit_row
        assert client.delete(f'/api/classroom/incidents/drafts/{incident_id}').status_code==404
    finally:db.close()

def test_attendance_ui_payload_attribution_and_room_visit_history():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        visiting=Room(centre_id=centre.id,name='Visit');db.add(visiting);db.commit();client=TestClient(app);paired(client,room);base={'child_id':children[0].id,'staff_id':staff.id}
        assert client.post('/api/classroom/presence',json={**base,'room_id':room.id,'action':'arrive'}).status_code==200
        assert client.post('/api/classroom/presence',json={**base,'room_id':visiting.id,'action':'visit'}).status_code==200
        assert client.post('/api/classroom/presence',json={**base,'room_id':visiting.id,'action':'end_visit'}).status_code==200
        assert client.post('/api/classroom/presence',json={**base,'room_id':room.id,'action':'depart'}).status_code==200
        attendance=db.query(Attendance).one();visit=db.query(RoomVisit).one();assert attendance.recorded_by_staff_id==staff.id and attendance.device_id
        assert visit.started_by_staff_id==staff.id and visit.ended_by_staff_id==staff.id and visit.device_id and visit.ended_at
        actions=db.query(Audit).filter_by(entity='attendance',actor_id=staff.id).all();assert {x.action for x in actions}=={'arrive','visit','end_visit','depart'}
    finally:db.close()

def test_parent_selected_day_export_matches_attendance_sleep_and_care():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);paired(client,room);child=children[0];presence={'child_id':child.id,'room_id':room.id,'staff_id':staff.id}
        assert client.post('/api/classroom/presence',json={**presence,'action':'arrive'}).status_code==200
        food={'client_operation_id':'export-food-batch-001','room_id':room.id,'staff_id':staff.id,'meal':'Lunch','rows':[{'child_id':child.id,'food':'Pasta','servings':[1]}]};assert client.post('/api/classroom/food-batch',json=food).status_code==200
        common={'child_ids':[child.id],'room_id':room.id,'staff_id':staff.id}
        for op,action in [('export-sleep-put-01','put_down'),('export-sleep-asleep','fell_asleep'),('export-sleep-wake01','wake'),('export-sleep-gotup1','got_up')]:assert client.post('/api/classroom/sleep',json={**common,'client_id':op,'action':action}).status_code==200
        assert client.post('/api/classroom/presence',json={**presence,'action':'depart'}).status_code==200
        assert client.post('/api/auth/parent/login',json={'login':'p','pin':'123456'}).status_code==200
        csv=client.get(f'/api/parent/children/{child.id}/export?day={client.get("/api/parent/me").json()["today"]}').text
        assert 'Drop off' in csv and 'Pick up' in csv and 'Sleep' in csv and 'Food' in csv and 'Pasta' in csv
    finally:db.close()

def test_branding_logo_upload_serve_and_remove():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        from PIL import Image
        image=Image.new('RGB',(2,2),(40,120,80));buffer=io.BytesIO();image.save(buffer,format='PNG')
        client=TestClient(app);assert client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        uploaded=client.post('/api/admin/branding/logo',files={'file':('centre.png',buffer.getvalue(),'image/png')});assert uploaded.status_code==200
        served=client.get(uploaded.json()['logo_url']);assert served.status_code==200 and served.headers['content-type']=='image/webp'
        assert client.delete('/api/admin/branding/logo').status_code==200
        assert client.get(uploaded.json()['logo_url']).status_code==404
    finally:db.close()

def test_production_startup_guard_rejects_defaults(monkeypatch):
    monkeypatch.setattr(main_module,'APP_ENV','production');monkeypatch.setattr(main_module,'SECRET','development-only-change-me');monkeypatch.setattr(main_module,'secure_cookie',False)
    with pytest.raises(RuntimeError):main_module.seed()
    monkeypatch.setattr(main_module,'SECRET','x'*40);monkeypatch.setattr(main_module,'secure_cookie',True)
    monkeypatch.setenv('DEMO_SEED','false');monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://user:unique@db/app');monkeypatch.setenv('PUBLIC_ORIGIN','https://example.test')
    assert main_module.seed() is None

def test_fixed_account_roles_enforce_management_boundaries_and_revoke_sessions():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        admin_client=TestClient(app)
        assert admin_client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        office=admin_client.post('/api/admin/accounts',json={'email':'office@test','password':'office-pass','role':'administration','active':True}).json()
        teacher=admin_client.post('/api/admin/accounts',json={'email':'teacher@test','password':'teacher-pass','role':'teacher','active':True}).json()
        assert admin_client.get('/api/admin/accounts').status_code==200
        assert admin_client.patch(f'/api/admin/accounts/{office["id"]}',json={'email':'office-updated@test'}).status_code==200
        assert admin_client.get('/api/admin/audit').status_code==200
        assert admin_client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Admin tablet'}).status_code==200
        office_client=TestClient(app);assert office_client.post('/api/auth/admin/login',json={'email':'office-updated@test','password':'office-pass'}).status_code==200
        assert office_client.get('/api/auth/account/me').json()['role']=='administration'
        assert office_client.get('/api/admin/bootstrap').status_code==200
        assert office_client.post('/api/admin/children',json={'first_name':'Office child'}).status_code==200
        assert office_client.post('/api/admin/staff',json={'first_name':'Office','last_name':'Teacher','pin':'4321'}).status_code==200
        assert office_client.get('/api/admin/accounts').status_code==403
        assert office_client.post('/api/admin/rooms',json={'name':'Forbidden'}).status_code==403
        assert office_client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Forbidden'}).status_code==403
        assert office_client.patch('/api/admin/branding',json={'display_name':'Forbidden'}).status_code==403
        assert office_client.post('/api/admin/devices/not-a-device/revoke').status_code==403
        assert office_client.patch('/api/admin/events/not-an-event/attribution',json={'performed_by_id':staff.id,'reason':'Not permitted'}).status_code==403
        assert office_client.post(f'/api/admin/staff/{staff.id}/pin-reset',json={'account_password':'office-pass','pin':'4321'}).status_code==200
        assert office_client.post(f'/api/admin/staff/{staff.id}/pin-reset',json={'account_password':'wrong','pin':'4321'}).status_code==403
        teacher_client=TestClient(app);assert teacher_client.post('/api/auth/admin/login',json={'email':'teacher@test','password':'teacher-pass'}).status_code==200
        assert teacher_client.get('/api/auth/account/me').json()['role']=='teacher'
        assert teacher_client.get('/api/admin/bootstrap').status_code==403
        assert teacher_client.get('/api/admin/accounts').status_code==403
        assert teacher_client.get('/api/admin/events').status_code==403
        assert teacher_client.get('/api/admin/audit').status_code==403
        assert teacher_client.post('/api/admin/children',json={'first_name':'Forbidden'}).status_code==403
        assert teacher_client.post('/api/admin/staff',json={'first_name':'Forbidden','last_name':'Teacher'}).status_code==403
        assert teacher_client.patch('/api/admin/branding',json={'display_name':'Forbidden'}).status_code==403
        assert teacher_client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Forbidden'}).status_code==403
        assert teacher_client.post('/api/admin/devices/not-a-device/revoke').status_code==403
        assert teacher_client.patch('/api/admin/events/not-an-event/attribution',json={'performed_by_id':staff.id,'reason':'Not permitted'}).status_code==403
        assert admin_client.patch(f'/api/admin/accounts/{teacher["id"]}',json={'role':'administration'}).status_code==200
        assert teacher_client.get('/api/auth/account/me').status_code==401
        assert admin_client.post(f'/api/admin/accounts/{teacher["id"]}/password-reset',json={'current_password':'secret','new_password':'teacher-new-pass','confirm_new_password':'teacher-new-pass'}).status_code==200
        assert teacher_client.post('/api/auth/admin/login',json={'email':'teacher@test','password':'teacher-pass'}).status_code==401
        assert TestClient(app).post('/api/auth/admin/login',json={'email':'teacher@test','password':'teacher-new-pass'}).status_code==200
        assert admin_client.patch(f'/api/admin/accounts/{account.id}',json={'active':False}).status_code==409
        assert office['role']=='administration'
    finally:db.close()

def test_account_password_sessions_cross_centre_and_restricted_audit_scope():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        admin_client=TestClient(app)
        assert admin_client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        office=admin_client.post('/api/admin/accounts',json={'email':'office@test','password':'office-pass','role':'administration','active':True}).json()
        teacher=admin_client.post('/api/admin/accounts',json={'email':'teacher@test','password':'teacher-pass','role':'teacher','active':True}).json()

        other_account=Account(centre_id=other_room.centre_id,email='other@test',password_hash=pwd.hash('other-pass'),role='admin')
        db.add(other_account);db.commit()

        assert admin_client.post('/api/admin/accounts',json={'email':'too-long@test','password':'x'*73,'role':'teacher'}).status_code==422
        assert admin_client.patch(f'/api/admin/accounts/{other_account.id}',json={'active':False}).status_code==404
        assert admin_client.post(f'/api/admin/accounts/{teacher["id"]}/password-reset',json={'current_password':'wrong','new_password':'teacher-next','confirm_new_password':'teacher-next'}).status_code==403

        office_current=TestClient(app)
        office_other=TestClient(app)
        assert office_current.post('/api/auth/admin/login',json={'email':'office@test','password':'office-pass'}).status_code==200
        assert office_other.post('/api/auth/admin/login',json={'email':'office@test','password':'office-pass'}).status_code==200
        changed=office_current.post('/api/auth/account/password',json={'current_password':'office-pass','new_password':'office-next','confirm_new_password':'office-next'})
        assert changed.status_code==200 and changed.json()['current_session_kept']
        assert office_current.get('/api/auth/account/me').status_code==200
        assert office_other.get('/api/auth/account/me').status_code==401
        assert TestClient(app).post('/api/auth/admin/login',json={'email':'office@test','password':'office-pass'}).status_code==401
        assert TestClient(app).post('/api/auth/admin/login',json={'email':'office@test','password':'office-next'}).status_code==200

        device_client=TestClient(app)
        paired(device_client,room)
        assert device_client.post('/api/classroom/presence',json={'child_id':children[0].id,'room_id':room.id,'action':'arrive','staff_id':staff.id}).status_code==200
        admin_audit=admin_client.get('/api/admin/audit').json()
        office_audit=office_current.get('/api/admin/audit').json()
        assert any(item['entity']=='account' for item in admin_audit)
        assert any(item['entity']=='attendance' and item['action']=='arrive' for item in office_audit)
        assert all((item['entity'],item['action']) in {('attendance','arrive'),('attendance','depart'),('attendance','visit'),('attendance','end_visit'),('incident','draft_discarded')} for item in office_audit)
    finally:db.close()

def test_account_logout_preserves_paired_device_and_login_fails_closed():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        legacy=Account(centre_id=centre.id,email='legacy@test',password_hash=pwd.hash('legacy-pass'),role='legacy')
        db.add(legacy);db.commit()
        client=TestClient(app)
        assert client.post('/api/auth/admin/login',json={'email':'a@test','password':'x'*73}).status_code==401
        assert client.post('/api/auth/admin/login',json={'email':'legacy@test','password':'legacy-pass'}).status_code==401
        assert db.query(AppSession).filter(AppSession.subject_id==legacy.id).count()==0

        paired(client,room)
        assert client.get('/api/auth/account/me').status_code==200
        assert client.get('/api/classroom/bootstrap').status_code==200
        device_token=client.cookies.get('device')
        assert device_token
        device_session=db.scalar(select(AppSession).where(AppSession.token_hash==hashlib.sha256(device_token.encode()).hexdigest(),AppSession.subject_type=='device'))
        assert device_session is not None and device_session.revoked_at is None

        assert client.post('/api/auth/account/logout').status_code==200
        assert client.get('/api/auth/account/me').status_code==401
        assert client.get('/api/classroom/bootstrap').status_code==200
        db.refresh(device_session)
        assert device_session.revoked_at is None
    finally:db.close()

def test_family_management_activity_correction_and_immediate_sleep():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        admin=TestClient(app);assert admin.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        family=admin.post('/api/admin/families',json={'name':'New family','login':'new-family','pin':'654321','child_ids':[children[0].id]}).json()
        assert family['children'][0]['id']==children[0].id
        assert admin.patch(f'/api/admin/families/{family["id"]}',json={'active':False,'child_ids':[children[1].id]}).status_code==200
        assert admin.post(f'/api/admin/families/{family["id"]}/pin-reset',json={'account_password':'wrong','pin':'111111'}).status_code==403
        assert admin.post(f'/api/admin/families/{family["id"]}/pin-reset',json={'account_password':'secret','pin':'111111'}).status_code==200
        assert TestClient(app).post('/api/auth/parent/login',json={'login':'new-family','pin':'111111'}).status_code==401

        device=TestClient(app);paired(device,room)
        event=device.post('/api/classroom/events',json={'client_id':'correctable-event-001','child_ids':[children[0].id],'type':'nappy','room_id':room.id,'performed_by_id':staff.id,'data':{'outcome':'wet'}}).json()['events'][0]
        office=admin.post('/api/admin/accounts',json={'email':'office@test','password':'office-pass','role':'administration'}).json()
        office_client=TestClient(app);assert office_client.post('/api/auth/admin/login',json={'email':'office@test','password':'office-pass'}).status_code==200
        assert office_client.get('/api/admin/activity').status_code==200
        corrected=office_client.patch(f'/api/admin/activity/events/{event["id"]}',json={'reason':'Corrected entry','data':{'outcome':'soiled'}})
        assert corrected.status_code==200 and corrected.json()['revision']==2
        assert db.query(Audit).filter_by(entity='event',entity_id=event['id'],action='ordinary_corrected').one().reason=='Corrected entry'
        assert office_client.patch(f'/api/admin/activity/events/{event["id"]}',json={'reason':'No generic data','data':{'unexpected':'value'}}).status_code==422
        assert office_client.patch('/api/admin/activity/not-an-audit',json={'reason':'no'}).status_code==404

        medicine=Event(centre_id=centre.id,room_id=room.id,child_id=children[0].id,type='medicine',effective_at=now(),client_id='test-medicine-event',data={},finalised=True)
        db.add(medicine);db.commit()
        assert office_client.patch(f'/api/admin/activity/events/{medicine.id}',json={'reason':'No medicine correction'}).status_code==409

        immediate=device.post('/api/classroom/sleep',json={'client_id':'immediate-sleep-001','child_ids':[children[0].id],'room_id':room.id,'action':'fell_asleep','staff_id':staff.id})
        assert immediate.status_code==200 and immediate.json()['sessions'][0]['session_id']
        assert device.post('/api/classroom/sleep',json={'client_id':'immediate-sleep-001','child_ids':[children[0].id],'room_id':room.id,'action':'fell_asleep','staff_id':staff.id}).json()['idempotent']
        session=db.query(SleepSession).filter_by(child_id=children[0].id).one()
        assert office_client.patch(f'/api/admin/activity/sleep-sessions/{session.id}',json={'reason':'Impossible sleep order','got_up_at':(session.put_down_at-timedelta(minutes=1)).isoformat()}).status_code==422
        assert office_client.patch(f'/api/admin/activity/sleep-sessions/{session.id}',json={'reason':'Clarified sleep note','note':'Settled quickly'}).status_code==200
        assert device.post('/api/classroom/sleep',json={'client_id':'sleep-check-001','child_ids':[children[0].id],'room_id':room.id,'action':'check','staff_id':staff.id}).status_code==200
        check=db.query(SleepCheck).filter_by(sleep_session_id=session.id).one()
        assert office_client.patch(f'/api/admin/activity/sleep-checks/{check.id}',json={'reason':'Bad enum','warmth':'unsafe'}).status_code==422
        assert office_client.patch(f'/api/admin/activity/sleep-checks/{check.id}',json={'reason':'Corrected check','warmth':'warm'}).status_code==200

        visitor_room=Room(centre_id=centre.id,name='Visitor room');db.add(visitor_room);db.commit()
        assert device.post('/api/classroom/presence',json={'child_id':children[1].id,'room_id':room.id,'action':'arrive','staff_id':staff.id}).status_code==200
        attendance=db.query(Attendance).filter_by(child_id=children[1].id).one()
        assert office_client.patch(f'/api/admin/activity/attendance/{attendance.id}',json={'reason':'Impossible departure','departed_at':(attendance.arrived_at-timedelta(minutes=1)).isoformat()}).status_code==422
        assert office_client.patch(f'/api/admin/activity/attendance/{attendance.id}',json={'reason':'Corrected attendance attribution','recorded_by_staff_id':staff.id}).status_code==200
        assert device.post('/api/classroom/presence',json={'child_id':children[1].id,'room_id':visitor_room.id,'action':'visit','staff_id':staff.id}).status_code==200
        assert device.post('/api/classroom/presence',json={'child_id':children[1].id,'room_id':visitor_room.id,'action':'end_visit','staff_id':staff.id}).status_code==200
        recent=device.get('/api/classroom/bootstrap').json()['recent_visitors']
        assert children[1].id in recent[visitor_room.id]
        assert all(item['child_id']==children[0].id for item in office_client.get(f'/api/admin/activity?child_id={children[0].id}').json()['items'] if item.get('child_id'))
        assert office_client.get('/api/admin/activity?category=management').status_code==403
    finally:db.close()

def test_activity_categories_local_dates_and_source_filters_before_limit():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        client=TestClient(app);assert client.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        boundary=datetime(2026,8,30,12,0,tzinfo=timezone.utc)
        target=Event(centre_id=centre.id,room_id=room.id,child_id=children[0].id,type='nappy',effective_at=boundary,client_id='target-local-boundary',data={'outcome':'wet'})
        db.add(target)
        for index in range(30):db.add(Event(centre_id=centre.id,room_id=room.id,child_id=children[1].id,type='nappy',effective_at=now()+timedelta(minutes=index),client_id=f'unrelated-{index}',data={'outcome':'dry'}))
        db.add_all([Audit(centre_id=centre.id,entity='child',entity_id=children[0].id,action='updated',after={}),Audit(centre_id=centre.id,entity='account',entity_id=account.id,action='password_reset',after={}),Audit(centre_id=centre.id,entity='future_sensitive',entity_id='unknown',action='future_action',after={})]);db.commit()
        assert any(item['id']==target.id for item in client.get(f'/api/admin/activity?child_id={children[0].id}&limit=1').json()['items'])
        assert any(item['id']==target.id for item in client.get('/api/admin/activity?from_date=2026-08-31&to_date=2026-08-31').json()['items'])
        assert not any(item['id']==target.id for item in client.get('/api/admin/activity?from_date=2026-08-30&to_date=2026-08-30').json()['items'])
        management=client.get('/api/admin/activity?category=management').json()['items'];security=client.get('/api/admin/activity?category=security').json()['items']
        assert all(item['category']=='management' for item in management) and any(item['entity']=='child' for item in management)
        assert all(item['category']=='security' for item in security) and any(item['entity']=='future_sensitive' for item in security)
        office=client.post('/api/admin/accounts',json={'email':'office-filter@test','password':'office-pass','role':'administration'}).json();office_client=TestClient(app);assert office_client.post('/api/auth/admin/login',json={'email':'office-filter@test','password':'office-pass'}).status_code==200
        assert office_client.get('/api/admin/activity?category=security').status_code==403
    finally:db.close()

def test_recent_visitors_excludes_current_visitors_before_taking_five():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        device=TestClient(app);paired(device,room)
        extra=[Child(centre_id=centre.id,room_id=room.id,first_name=f'Visitor{index}') for index in range(7)]
        db.add_all(extra);db.flush()
        for index,child in enumerate(extra):
            when=now()-timedelta(minutes=index)
            active=index<2
            attendance=Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=when,departed_at=None,visit_room_id=room.id if active else None,visit_started_at=when,visit_ended_at=None if active else when+timedelta(seconds=1),recorded_by_staff_id=staff.id)
            db.add(attendance);db.flush();db.add(RoomVisit(centre_id=centre.id,attendance_id=attendance.id,child_id=child.id,room_id=room.id,started_at=when,ended_at=None if active else when+timedelta(seconds=1),started_by_staff_id=staff.id))
        db.commit()
        assert device.get('/api/classroom/bootstrap').json()['recent_visitors'][room.id]==[child.id for child in extra[2:7]]
    finally:db.close()

def test_corrections_preserve_lifecycle_shape_and_activity_candidates():
    db,centre,account,room,other_room,staff,children,parent=setup()
    try:
        admin=TestClient(app);assert admin.post('/api/auth/admin/login',json={'email':'a@test','password':'secret'}).status_code==200
        device=TestClient(app);paired(device,room)
        assert device.post('/api/classroom/presence',json={'child_id':children[0].id,'room_id':room.id,'action':'arrive','staff_id':staff.id}).status_code==200
        attendance=db.query(Attendance).filter_by(child_id=children[0].id).one()
        assert admin.patch(f'/api/admin/activity/attendance/{attendance.id}',json={'reason':'Not a departure','departed_at':(attendance.arrived_at+timedelta(minutes=10)).isoformat()}).status_code==422
        visitor_room=Room(centre_id=centre.id,name='Correction visitor room');db.add(visitor_room);db.commit()
        assert device.post('/api/classroom/presence',json={'child_id':children[0].id,'room_id':visitor_room.id,'action':'visit','staff_id':staff.id}).status_code==200
        visit=db.query(RoomVisit).filter_by(attendance_id=attendance.id).one()
        assert admin.patch(f'/api/admin/activity/room-visits/{visit.id}',json={'reason':'Not an operational end','ended_at':(visit.started_at+timedelta(minutes=5)).isoformat()}).status_code==422
        assert device.post('/api/classroom/presence',json={'child_id':children[0].id,'room_id':visitor_room.id,'action':'end_visit','staff_id':staff.id}).status_code==200
        db.refresh(attendance);db.refresh(visit)
        corrected_start=visit.started_at+timedelta(minutes=1);corrected_end=visit.ended_at+timedelta(minutes=1)
        assert admin.patch(f'/api/admin/activity/room-visits/{visit.id}',json={'reason':'Corrected completed visit','started_at':corrected_start.isoformat(),'ended_at':corrected_end.isoformat()}).status_code==200
        db.refresh(attendance);db.refresh(visit)
        assert attendance.visit_started_at==visit.started_at and attendance.visit_ended_at==visit.ended_at
        other_staff=Staff(centre_id=centre.id,first_name='Other',last_name='Teacher',pin_hash=pwd.hash('4567'));db.add(other_staff);db.commit()
        assert device.post('/api/classroom/presence',json={'child_id':children[0].id,'room_id':visitor_room.id,'action':'visit','staff_id':staff.id}).status_code==200
        assert device.post('/api/classroom/presence',json={'child_id':children[0].id,'room_id':visitor_room.id,'action':'end_visit','staff_id':staff.id}).status_code==200
        db.refresh(attendance)
        current_started,current_ended,current_room=attendance.visit_started_at,attendance.visit_ended_at,attendance.last_visit_room_id
        attribution=admin.patch(f'/api/admin/activity/room-visits/{visit.id}',json={'reason':'Corrected historical end attribution','ended_by_staff_id':other_staff.id})
        assert attribution.status_code==200 and db.query(Audit).filter_by(entity='room_visit',entity_id=visit.id,action='ordinary_corrected').count()>=2
        db.refresh(attendance);db.refresh(visit)
        assert (attendance.visit_started_at,attendance.visit_ended_at,attendance.last_visit_room_id)==(current_started,current_ended,current_room)
        assert visit.ended_by_staff_id==other_staff.id
        assert admin.patch(f'/api/admin/activity/room-visits/{visit.id}',json={'reason':'Old visit timestamp is not represented','ended_at':(visit.ended_at+timedelta(seconds=1)).isoformat()}).status_code==409
        assert device.post('/api/classroom/sleep',json={'client_id':'shape-sleep','child_ids':[children[1].id],'room_id':room.id,'action':'put_down','staff_id':staff.id}).status_code==200
        session=db.query(SleepSession).filter_by(child_id=children[1].id).one()
        assert admin.patch(f'/api/admin/activity/sleep-sessions/{session.id}',json={'reason':'Not asleep transition','fell_asleep_at':(session.put_down_at+timedelta(minutes=2)).isoformat()}).status_code==422
        assert admin.patch(f'/api/admin/activity/sleep-sessions/{session.id}',json={'reason':'Not wake transition','woke_at':(session.put_down_at+timedelta(minutes=3)).isoformat()}).status_code==422
        assert admin.patch(f'/api/admin/activity/sleep-sessions/{session.id}',json={'reason':'Not get-up transition','got_up_at':(session.put_down_at+timedelta(minutes=4)).isoformat()}).status_code==422
        assert admin.patch(f'/api/admin/activity/sleep-sessions/{session.id}',json={'reason':'No wake metadata yet','quality':'rested'}).status_code==422
        assert admin.patch(f'/api/admin/activity/sleep-sessions/{session.id}',json={'reason':'No closure attribution yet','closed_by_staff_id':staff.id}).status_code==422
        target=Event(centre_id=centre.id,room_id=room.id,child_id=children[0].id,type='staff_note',effective_at=now()-timedelta(days=1),client_id='older-search-match',data={'note':'needle phrase'})
        db.add(target)
        for index in range(240):db.add(Audit(centre_id=centre.id,entity='account',entity_id=account.id,action='password_reset',after={},created_at=now()+timedelta(minutes=index)))
        management=Audit(centre_id=centre.id,entity='child',entity_id=children[0].id,action='updated',after={},created_at=now()-timedelta(days=1));db.add(management)
        for index in range(30):db.add(Event(centre_id=centre.id,room_id=room.id,child_id=children[1].id,type='staff_note',effective_at=now()+timedelta(minutes=index),client_id=f'newer-search-{index}',data={'note':'other'}))
        db.commit()
        assert any(item['id']==management.id for item in admin.get('/api/admin/activity?category=management&limit=20').json()['items'])
        assert any(item['id']==target.id for item in admin.get('/api/admin/activity?search=needle&limit=1').json()['items'])
    finally:db.close()
def test_admin_management_rooms_children_and_staff():
    db,centre,account,room,other_room,staff,children,parent=setup()

    try:
        client=TestClient(app)

        assert client.post(
            '/api/auth/admin/login',
            json={
                'email':'a@test',
                'password':'secret'
            }
        ).status_code==200

        created_room=client.post(
            '/api/admin/rooms',
            json={
                'name':'Demo New Room',
                'accent':'#123ABC',
                'icon':'🚀'
            }
        )

        assert created_room.status_code==200
        room_id=created_room.json()['id']

        edited_room=client.patch(
            f'/api/admin/rooms/{room_id}',
            json={
                'name':'Demo Edited Room',
                'accent':'#ABC123',
                'icon':'⭐'
            }
        )

        assert edited_room.status_code==200
        assert edited_room.json()['name']=='Demo Edited Room'

        child_response=client.post(
            '/api/admin/children',
            json={
                'first_name':'Demo',
                'last_name':'Child',
                'preferred_name':'Demi',
                'dob':'2023-05-01',
                'room_id':room_id,
                'active':True
            }
        )

        assert child_response.status_code==200
        child_id=child_response.json()['id']

        bootstrap=client.get(
            '/api/admin/bootstrap'
        ).json()

        created_child=next(
            item
            for item in bootstrap['children']
            if item['id']==child_id
        )

        assert created_child['first_name']=='Demo'
        assert created_child['preferred_name']=='Demi'
        assert created_child['room_id']==room_id

        assert client.patch(
            f'/api/admin/children/{child_id}',
            json={'active':False}
        ).status_code==200

        staff_response=client.post(
            '/api/admin/staff',
            json={
                'first_name':'Demo',
                'last_name':'Teacher',
                'preferred_name':'DT',
                'employment_type':'reliever',
                'active':True,
                'pin':'4567'
            }
        )

        assert staff_response.status_code==200
        staff_id=staff_response.json()['id']

        db.expire_all()
        created_staff=db.get(Staff,staff_id)

        assert created_staff is not None
        assert created_staff.pin_hash!='4567'
        assert pwd.verify(
            '4567',
            created_staff.pin_hash
        )

        wrong=client.post(
            f'/api/admin/staff/{staff_id}/pin-reset',
            json={
                'account_password':'wrong',
                'pin':'7654'
            }
        )

        assert wrong.status_code==403

        good=client.post(
            f'/api/admin/staff/{staff_id}/pin-reset',
            json={
                'account_password':'secret',
                'pin':'7654'
            }
        )

        assert good.status_code==200

        db.expire_all()
        assert pwd.verify(
            '7654',
            db.get(Staff,staff_id).pin_hash
        )

        blocked_delete=client.post(
            f'/api/admin/rooms/{room_id}/delete',
            json={'admin_password':'secret'}
        )

        assert blocked_delete.status_code==409

        empty_room=client.post(
            '/api/admin/rooms',
            json={
                'name':'Disposable Room',
                'accent':'#112233',
                'icon':'🧪'
            }
        ).json()

        assert client.post(
            f"/api/admin/rooms/{empty_room['id']}/delete",
            json={'admin_password':'wrong'}
        ).status_code==403

        assert client.post(
            f"/api/admin/rooms/{empty_room['id']}/delete",
            json={'admin_password':'secret'}
        ).status_code==200

        db.expire_all()

        assert db.query(Audit).filter(
            Audit.entity.in_([
                'room',
                'child',
                'staff'
            ])
        ).count()>=6

    finally:
        db.close()

def test_admin_archive_visibility_and_inactive_staff_guard():
    db,centre,account,room,other_room,staff,children,parent=setup()

    try:
        client=TestClient(app)

        paired(client,room)

        child=children[0]

        # An operationally present child cannot simply disappear
        # from classroom management by being archived.
        arrived=client.post(
            '/api/classroom/presence',
            json={
                'child_id':child.id,
                'room_id':room.id,
                'action':'arrive',
                'staff_id':staff.id
            }
        )

        assert arrived.status_code==200

        blocked=client.patch(
            f'/api/admin/children/{child.id}',
            json={'active':False}
        )

        assert blocked.status_code==409
        assert 'Depart' in blocked.text

        departed=client.post(
            '/api/classroom/presence',
            json={
                'child_id':child.id,
                'room_id':room.id,
                'action':'depart',
                'staff_id':staff.id
            }
        )

        assert departed.status_code==200

        archived=client.patch(
            f'/api/admin/children/{child.id}',
            json={'active':False}
        )

        assert archived.status_code==200

        classroom=client.get(
            '/api/classroom/bootstrap'
        )

        assert classroom.status_code==200

        visible_ids={
            item['id']
            for item in classroom.json()['children']
        }

        assert child.id not in visible_ids

        # Historical staff remain in the DB, but cannot continue
        # recording new ordinary care after deactivation.
        disabled=client.patch(
            f'/api/admin/staff/{staff.id}',
            json={'active':False}
        )

        assert disabled.status_code==200

        classroom=client.get(
            '/api/classroom/bootstrap'
        ).json()

        staff_ids={
            item['id']
            for item in classroom['staff']
        }

        assert staff.id not in staff_ids

        ordinary=client.post(
            '/api/classroom/events',
            json={
                'client_id':'inactive-staff-op-001',
                'child_ids':[children[1].id],
                'type':'sunscreen',
                'room_id':room.id,
                'performed_by_id':staff.id,
                'data':{
                    'application':'exposed skin'
                }
            }
        )

        assert ordinary.status_code==422
        assert 'active staff' in ordinary.text

    finally:
        db.close()
