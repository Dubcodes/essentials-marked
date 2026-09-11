import os
from datetime import timedelta
from zoneinfo import ZoneInfo

os.environ['DATABASE_URL']='sqlite:///./test.db'
os.environ['DEMO_SEED']='false'

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Base,engine,SessionLocal
from app.main import app,pwd,soften_parent_text,centre_local_datetime,audit_category,audit_activity_out,utc
from app.models import Centre,Account,Room,Staff,Child,Parent,ParentChild,Attendance,Device,Signature,Audit,ParentNote,CentreSafetyCheck,CentreSafetyCheckRoom,now

def setup_020():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);db=SessionLocal()
    centre=Centre(name='A',timezone='Pacific/Auckland');other=Centre(name='B');db.add_all([centre,other]);db.flush()
    admin=Account(centre_id=centre.id,login_id='admin',password_hash=pwd.hash('secret'),role='admin')
    office=Account(centre_id=centre.id,login_id='office',password_hash=pwd.hash('secret'),role='administration')
    teacher_account=Account(centre_id=centre.id,login_id='teacher',password_hash=pwd.hash('secret'),role='teacher')
    other_admin=Account(centre_id=other.id,login_id='other-admin',password_hash=pwd.hash('secret'),role='admin')
    room=Room(centre_id=centre.id,name='Harakeke',accent='#123456',icon='🌿');visit=Room(centre_id=centre.id,name='Kōwhai',accent='#654321',icon='🌼')
    staff=Staff(centre_id=centre.id,first_name='Sarah',last_name='Teacher',pin_hash=pwd.hash('1234'))
    inactive=Staff(centre_id=centre.id,first_name='Old',last_name='Teacher',pin_hash=pwd.hash('1234'),active=False)
    child=Child(centre_id=centre.id,room_id=room.id,first_name='Kamishita',last_name='Ross');absent=Child(centre_id=centre.id,room_id=room.id,first_name='Shitake',last_name='Lee')
    parent=Parent(centre_id=centre.id,name='Parent',login='family',pin_hash=pwd.hash('123456'))
    db.add_all([admin,office,teacher_account,other_admin,room,visit,staff,inactive,child,absent,parent]);db.flush();db.add(ParentChild(parent_id=parent.id,child_id=child.id));db.commit()
    return db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent

def login(client,identifier='admin'):
    assert client.post('/api/auth/admin/login',json={'email':identifier,'password':'secret'}).status_code==200

def attendance_client(room):
    client=TestClient(app);login(client);pair=client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Harakeke Sign-in','mode':'attendance'}).json();assert client.post('/api/device/pair',json={'token':pair['token'],'challenge':pair['challenge']}).status_code==200;return client

def test_operational_settings_relationship_enforcement_and_minimal_bootstrap():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        client=TestClient(app);login(client)
        settings=client.get('/api/admin/settings').json();assert settings['parent_history_days']==7 and settings['sleep_check_minutes']==10 and settings['attendance_relationship_required'] is True
        assert client.patch('/api/admin/operational-settings',json={'parent_history_days':30,'sleep_check_minutes':4,'attendance_relationship_required':False}).status_code==422
        saved=client.patch('/api/admin/operational-settings',json={'parent_history_days':30,'sleep_check_minutes':5,'attendance_relationship_required':False});assert saved.status_code==200
        kiosk=attendance_client(room);boot=kiosk.get('/api/attendance/bootstrap').json()
        assert boot['relationship_required'] is False and boot['assigned_room']=={'id':room.id,'name':'Harakeke','accent':'#123456','icon':'🌿'} and boot['centre']['timezone']=='Pacific/Auckland'
        payload={'child_id':child.id,'room_id':room.id,'action':'sign_in','relationship':None,'signature_data':'data:image/png;base64,relationship-optional'}
        assert kiosk.post('/api/attendance/kiosk',json=payload).status_code==200
        centre.attendance_relationship_required=True;db.commit();assert kiosk.post('/api/attendance/kiosk',json={**payload,'child_id':absent.id}).status_code==422
    finally:db.close()

def test_parent_note_softening_original_admin_reveal_and_audit():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        assert soften_parent_text('this was shit')=='this was poo';assert soften_parent_text('shit!')=='poo!';assert soften_parent_text('Kamishita Shitake')=='Kamishita Shitake'
        parent_client=TestClient(app);assert parent_client.post('/api/auth/parent/login',json={'login':'family','pin':'123456'}).status_code==200
        original='Kamishita had a shit! Shitake mushrooms were fine.'
        created=parent_client.post('/api/parent/notes',json={'child_id':child.id,'body':original});assert created.status_code==200
        note_id=created.json()['id'];db.expire_all();assert db.get(ParentNote,note_id).body==original
        classroom=TestClient(app);login(classroom);pair=classroom.post('/api/admin/pairings',json={'room_id':room.id,'label':'Classroom'}).json();classroom.post('/api/device/pair',json={'token':pair['token'],'challenge':pair['challenge']})
        shown=classroom.get('/api/classroom/parent-notes').json()[0];assert shown['body']=='Kamishita had a poo! Shitake mushrooms were fine.'
        admin_client=TestClient(app);login(admin_client);activity=admin_client.get('/api/admin/activity?category=classroom&search=poo').json()['items'];assert activity and activity[0]['data']['body']==shown['body']
        revealed=admin_client.get(f'/api/admin/parent-notes/{note_id}/original');assert revealed.status_code==200 and revealed.json()['body']==original
        audit_row=db.scalar(select(Audit).where(Audit.action=='parent_note_original_viewed'));db.refresh(audit_row);assert original not in str(audit_row.after) and 'body' not in str(audit_row.after)
        office_client=TestClient(app);login(office_client,'office');assert office_client.get(f'/api/admin/parent-notes/{note_id}/original').status_code==403
    finally:db.close()

def test_stale_attendance_parent_confirmation_preserves_arrival_evidence():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        kiosk=attendance_client(room);device=db.scalar(select(Device).where(Device.mode=='attendance'))
        arrived=now()-timedelta(days=2);attendance=Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=arrived,source='parent_kiosk',device_id=device.id,signer_name='Original parent',signer_relationship='Mother');db.add(attendance);db.flush();db.add(Signature(centre_id=centre.id,parent_id=None,signer_name='Original parent',relationship='Mother',domain_type='attendance',domain_id=attendance.id,revision=1,purpose='kiosk_sign_in',signature_data='data:image/png;base64,original-sign-in'));db.commit()
        boot=kiosk.get('/api/attendance/bootstrap').json();row=next(item for item in boot['children'] if item['id']==child.id);assert row['stale_attendance'] is True and row['attendance_id']==attendance.id
        assert kiosk.post('/api/attendance/kiosk',json={'child_id':child.id,'room_id':room.id,'action':'sign_in','relationship':'Mother','signature_data':'data:image/png;base64,new-sign-in-blocked'}).status_code==409
        admin_client=TestClient(app);login(admin_client);attention=admin_client.get('/api/admin/bootstrap').json()['missing_sign_outs'];assert attention and attention[0]['attendance_id']==attendance.id
        local_pickup=(arrived+timedelta(hours=8)).astimezone(ZoneInfo(centre.timezone))
        base={'child_id':child.id,'attendance_id':attendance.id,'pickup_date':local_pickup.date().isoformat(),'pickup_time':local_pickup.strftime('%H:%M'),'relationship':'Caregiver','signature_data':'data:image/png;base64,missing-pickup-evidence'}
        assert kiosk.post('/api/attendance/missing-sign-out',json={**base,'signature_data':'short'}).status_code==422
        ok=kiosk.post('/api/attendance/missing-sign-out',json=base);assert ok.status_code==200
        db.expire_all();saved=db.get(Attendance,attendance.id);assert saved.arrived_at==attendance.arrived_at and saved.source=='parent_kiosk' and saved.device_id==device.id and saved.departed_at is not None
        signature=db.scalar(select(Signature).where(Signature.domain_id==attendance.id,Signature.purpose=='parent_missing_sign_out_confirmation'));assert signature and signature.relationship=='Caregiver'
        evidence=db.scalar(select(Audit).where(Audit.action=='parent_confirmed_missing_sign_out'));assert 'signature' not in str(evidence.after).lower()
        assert next(item for item in kiosk.get('/api/attendance/bootstrap').json()['children'] if item['id']==child.id)['stale_attendance'] is False
        assert admin_client.get('/api/admin/bootstrap').json()['missing_sign_outs']==[]
        assert admin_client.get(f'/api/admin/activity/attendance/{attendance.id}/signature?purpose=parent_missing_sign_out_confirmation').status_code==200
    finally:db.close()

def test_safety_check_pin_snapshot_mismatch_completion_and_access():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        attendance=Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=now()-timedelta(hours=1),visit_room_id=visit.id,visit_started_at=now()-timedelta(minutes=20),visit_ended_at=None);db.add(attendance);db.commit()
        teacher=TestClient(app);login(teacher,'teacher');assert teacher.post('/api/admin/safety-checks',json={'staff_id':staff.id,'staff_pin':'1234'}).status_code==403
        office_client=TestClient(app);login(office_client,'office');assert office_client.post('/api/admin/safety-checks',json={'staff_id':inactive.id,'staff_pin':'1234'}).status_code==404
        assert office_client.post('/api/admin/safety-checks',json={'staff_id':staff.id,'staff_pin':'0000'}).status_code==403
        started=office_client.post('/api/admin/safety-checks',json={'staff_id':staff.id,'staff_pin':'1234'});assert started.status_code==200 and 'pin' not in started.text.lower()
        check=started.json();room_state=next(item for item in check['rooms'] if item['room_id']==room.id);visit_state=next(item for item in check['rooms'] if item['room_id']==visit.id)
        assert room_state['expected_count']==0 and visit_state['expected_count']==1 and visit_state['expected_children'][0]['id']==child.id
        confirmed=office_client.post(f"/api/admin/safety-checks/{check['id']}/rooms/{visit.id}",json={'expected_count':1,'observed_count':1});assert confirmed.status_code==200
        attendance.visit_room_id=None;attendance.visit_ended_at=now();db.commit()
        snapshot=db.scalar(select(CentreSafetyCheckRoom).where(CentreSafetyCheckRoom.room_id==visit.id));assert snapshot.expected_count==1 and snapshot.expected_children[0]['id']==child.id
        assert office_client.post(f"/api/admin/safety-checks/{check['id']}/rooms/{room.id}",json={'expected_count':1,'observed_count':0}).status_code==422
        mismatch=office_client.post(f"/api/admin/safety-checks/{check['id']}/rooms/{room.id}",json={'expected_count':1,'observed_count':0,'note':'Investigating roster difference'});assert mismatch.status_code==200
        db.refresh(attendance);assert attendance.departed_at is None and attendance.room_id==room.id
        completed=office_client.post(f"/api/admin/safety-checks/{check['id']}/complete");assert completed.status_code==200 and completed.json()['status']=='completed' and completed.json()['has_mismatch'] is True
        other_client=TestClient(app);login(other_client,'other-admin');assert other_client.get(f"/api/admin/safety-checks/{check['id']}").status_code==404
    finally:db.close()

def test_safety_check_rejects_stale_expected_count_then_refreshes_and_confirms():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        db.add(Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=now()-timedelta(hours=1)));db.commit()
        client=TestClient(app);login(client,'office');started=client.post('/api/admin/safety-checks',json={'staff_id':staff.id,'staff_pin':'1234'}).json()
        shown=next(item for item in started['rooms'] if item['room_id']==room.id);assert shown['expected_count']==1
        db.add(Attendance(centre_id=centre.id,child_id=absent.id,room_id=room.id,arrived_at=now()));db.commit()
        stale=client.post(f"/api/admin/safety-checks/{started['id']}/rooms/{room.id}",json={'expected_count':1,'observed_count':1})
        assert stale.status_code==409 and 'Please recount' in stale.json()['detail']
        assert db.scalar(select(CentreSafetyCheckRoom).where(CentreSafetyCheckRoom.safety_check_id==started['id'],CentreSafetyCheckRoom.room_id==room.id)) is None
        refreshed=client.get(f"/api/admin/safety-checks/{started['id']}").json();fresh_room=next(item for item in refreshed['rooms'] if item['room_id']==room.id)
        assert fresh_room['expected_count']==2 and {item['id'] for item in fresh_room['expected_children']}=={child.id,absent.id}
        confirmed=client.post(f"/api/admin/safety-checks/{started['id']}/rooms/{room.id}",json={'expected_count':2,'observed_count':2});assert confirmed.status_code==200
    finally:db.close()

def test_old_safety_check_rejects_inactive_original_checker():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        client=TestClient(app);login(client,'office');started=client.post('/api/admin/safety-checks',json={'staff_id':staff.id,'staff_pin':'1234'}).json()
        check=db.get(CentreSafetyCheck,started['id']);check.started_at=now()-timedelta(minutes=31);staff.active=False;db.commit()
        denied=client.post(f"/api/admin/safety-checks/{check.id}/rooms/{room.id}",json={'expected_count':0,'observed_count':0,'staff_pin':'1234'})
        assert denied.status_code==409 and denied.json()['detail']=='The original checker is no longer active. Start a new safety check.'
        assert db.scalar(select(CentreSafetyCheckRoom).where(CentreSafetyCheckRoom.safety_check_id==check.id)) is None
    finally:db.close()

def test_old_safety_check_accepts_active_original_checker_pin():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        client=TestClient(app);login(client,'office');started=client.post('/api/admin/safety-checks',json={'staff_id':staff.id,'staff_pin':'1234'}).json()
        check=db.get(CentreSafetyCheck,started['id']);check.started_at=now()-timedelta(minutes=31);db.commit()
        confirmed=client.post(f"/api/admin/safety-checks/{check.id}/rooms/{room.id}",json={'expected_count':0,'observed_count':0,'staff_pin':'1234'})
        assert confirmed.status_code==200
        assert db.scalar(select(CentreSafetyCheckRoom).where(CentreSafetyCheckRoom.safety_check_id==check.id, CentreSafetyCheckRoom.room_id==room.id)) is not None
    finally:db.close()

def test_human_audit_display_omits_technical_ids_but_raw_data_preserves_them():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        cases=[
            ('centre_safety_check_room','confirmed','safety_check_id',{'safety_check_id':'safety-uuid','room_id':room.id,'expected_count':1,'observed_count':1,'match':True,'staff_id':staff.id}),
            ('attendance','parent_confirmed_missing_sign_out','attendance_id',{'attendance_id':'attendance-uuid','child_id':child.id,'relationship':'Mother','device_id':'device-uuid','previous_open':True}),
            ('parent_note','parent_note_original_viewed','note_id',{'note_id':'note-uuid','viewer_account_id':admin.id}),
        ]
        for entity,action,technical_field,after in cases:
            before={technical_field:'previous-technical-id'}
            item=Audit(centre_id=centre.id,entity=entity,entity_id='raw-entity-id',action=action,before=before,after=after,actor_id=admin.id);db.add(item);db.flush()
            output=audit_activity_out(item,db)
            assert technical_field not in output['display_data']
            assert technical_field not in output['display_before']
            assert output['data'][technical_field]==after[technical_field]
            assert output['before'][technical_field]=='previous-technical-id'
            assert output['entity_id']=='raw-entity-id'
        db.rollback()
    finally:db.close()

def test_activity_pairing_resolves_room_account_and_device_evidence():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        client=TestClient(app);login(client);pair=client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Hall tablet','mode':'attendance'});assert pair.status_code==200
        items=client.get('/api/admin/activity?category=security&search=Harakeke').json()['items'];created=next(item for item in items if item['entity']=='pairing')
        assert created['room']=='Harakeke' and created['actor']=='admin' and created['data']['mode']=='attendance'
        assert created['display_data']['room_id']=='Harakeke' and created['data']['room_id']==room.id
        kiosk=client.post('/api/device/pair',json={'token':pair.json()['token'],'challenge':pair.json()['challenge']});assert kiosk.status_code==200
    finally:db.close()

def test_new_audit_actions_are_explicitly_classified_and_unknowns_fail_closed():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        db.add_all([
            Audit(centre_id=centre.id,entity='centre',entity_id=centre.id,action='operational_settings_updated',after={'sleep_check_minutes':5},actor_id=admin.id),
            Audit(centre_id=centre.id,entity='parent_note',entity_id='note',action='parent_note_original_viewed',after={'viewer_account_id':admin.id},actor_id=admin.id),
            Audit(centre_id=centre.id,entity='parent_note',entity_id='note',action='submitted',after={'child_id':child.id},actor_id=parent.id),
            Audit(centre_id=centre.id,entity='future_domain',entity_id='future',action='future_action',after={},actor_id=admin.id)
        ]);db.commit()
        client=TestClient(app);login(client)
        management=client.get('/api/admin/activity?category=management').json()['items'];security=client.get('/api/admin/activity?category=security').json()['items']
        assert any(item['type']=='operational_settings_updated' for item in management)
        assert not any(item['type']=='operational_settings_updated' for item in security)
        assert any(item['type']=='parent_note_original_viewed' for item in security)
        assert not any(item['type']=='parent_note_original_viewed' for item in management)
        assert any(item['type']=='future_action' for item in security)
        assert not any(item['type']=='submitted' and item['entity']=='parent_note' for item in management+security)
        office_client=TestClient(app);login(office_client,'office')
        assert office_client.get('/api/admin/activity?category=management').status_code==403
        assert office_client.get('/api/admin/activity?category=security').status_code==403
    finally:db.close()

def test_known_020_operational_audit_is_management():
    assert audit_category(Audit(entity='centre',action='operational_settings_updated'))=='management'

def test_original_parent_note_view_is_security():
    assert audit_category(Audit(entity='parent_note',action='parent_note_original_viewed'))=='security'

def test_unknown_audit_action_fails_closed_to_security():
    assert audit_category(Audit(entity='future_domain',action='future_action'))=='security'

def test_missing_pickup_local_time_rejects_dst_gaps_and_requires_ambiguous_choice():
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException,match='does not exist'):centre_local_datetime('2026-09-27T02:30','Pacific/Auckland')
    with pytest.raises(HTTPException,match='occurs twice'):centre_local_datetime('2026-04-05T02:30','Pacific/Auckland')
    assert centre_local_datetime('2026-04-05T02:30','Pacific/Auckland',0)!=centre_local_datetime('2026-04-05T02:30','Pacific/Auckland',1)

def test_teacher_arrival_requires_parent_sign_in_recovery_before_pickup_and_keeps_attribution():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        arrived=now()-timedelta(hours=2);attendance=Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=arrived,recorded_by_staff_id=staff.id,source='classroom');db.add(attendance);db.commit()
        kiosk=attendance_client(room);boot=next(item for item in kiosk.get('/api/attendance/bootstrap').json()['children'] if item['id']==child.id);pending=boot['pending_attendance_confirmation']
        assert pending['phase']=='sign_in' and pending['recorded_by']=='Sarah T.' and pending['needs_departure_time'] is False
        normal={'child_id':child.id,'room_id':room.id,'action':'sign_out','relationship':'Caregiver','signature_data':'data:image/png;base64,normal-pickup'}
        assert kiosk.post('/api/attendance/kiosk',json=normal).status_code==409
        recovery={'child_id':child.id,'attendance_id':attendance.id,'phase':'sign_in','relationship':'Caregiver','signature_data':'data:image/png;base64,arrival-confirmation'}
        confirmed=kiosk.post('/api/attendance/missing-signature',json=recovery);assert confirmed.status_code==200 and confirmed.json()['next_confirmation'] is None
        db.expire_all();saved=db.get(Attendance,attendance.id);assert utc(saved.arrived_at)==utc(arrived) and saved.recorded_by_staff_id==staff.id and saved.source=='classroom' and saved.device_id is None
        evidence=db.scalar(select(Audit).where(Audit.action=='parent_confirmed_missing_sign_in'));assert evidence and 'signature' not in str(evidence.after).lower() and evidence.after['relationship']=='Caregiver'
        assert kiosk.post('/api/attendance/kiosk',json={**normal,'signature_data':recovery['signature_data']}).status_code==409
        assert kiosk.post('/api/attendance/kiosk',json=normal).status_code==200
        purposes={row.purpose for row in db.scalars(select(Signature).where(Signature.domain_id==attendance.id))};assert purposes=={'parent_missing_sign_in_confirmation','kiosk_sign_out'}
    finally:db.close()

def test_normal_parent_sign_in_is_complete_without_recovery():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        kiosk=attendance_client(room);signed=kiosk.post('/api/attendance/kiosk',json={'child_id':child.id,'room_id':room.id,'action':'sign_in','relationship':'Mother','signature_data':'data:image/png;base64,normal-arrival'});assert signed.status_code==200
        row=next(item for item in kiosk.get('/api/attendance/bootstrap').json()['children'] if item['id']==child.id)
        assert row['present'] is True and row['pending_attendance_confirmation'] is None
        signature=db.scalar(select(Signature).where(Signature.domain_id==signed.json()['id']));assert signature.purpose=='kiosk_sign_in'
    finally:db.close()

def test_closed_teacher_attendance_recovers_both_phases_in_order_with_fresh_signatures():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        arrived=now()-timedelta(hours=3);departed=now()-timedelta(hours=1);attendance=Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=arrived,departed_at=departed,recorded_by_staff_id=staff.id,source='classroom');db.add(attendance);db.commit();kiosk=attendance_client(room)
        first=next(item for item in kiosk.get('/api/attendance/bootstrap').json()['children'] if item['id']==child.id)['pending_attendance_confirmation'];assert first['phase']=='sign_in'
        shared={'child_id':child.id,'attendance_id':attendance.id,'relationship':'Mother','signature_data':'data:image/png;base64,first-phase'}
        arrival=kiosk.post('/api/attendance/missing-signature',json={**shared,'phase':'sign_in'});assert arrival.status_code==200 and arrival.json()['next_confirmation']['phase']=='sign_out' and arrival.json()['next_confirmation']['needs_departure_time'] is False
        assert kiosk.post('/api/attendance/missing-signature',json={**shared,'phase':'sign_out'}).status_code==409
        pickup=kiosk.post('/api/attendance/missing-signature',json={**shared,'phase':'sign_out','signature_data':'data:image/png;base64,second-phase'});assert pickup.status_code==200 and pickup.json()['next_confirmation'] is None
        db.expire_all();saved=db.get(Attendance,attendance.id);assert utc(saved.arrived_at)==utc(arrived) and utc(saved.departed_at)==utc(departed) and saved.recorded_by_staff_id==staff.id and saved.source=='classroom'
        signatures=list(db.scalars(select(Signature).where(Signature.domain_id==attendance.id)));assert len(signatures)==2 and len({item.signature_data for item in signatures})==2
        admin_client=TestClient(app);login(admin_client);assert admin_client.get('/api/admin/bootstrap').json()['attendance_signature_issues']==[]
    finally:db.close()

def test_recovery_evidence_flows_to_parent_activity_csv_and_scoped_viewers():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        attendance=Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=now()-timedelta(hours=2),departed_at=now()-timedelta(hours=1),recorded_by_staff_id=staff.id,source='classroom');db.add(attendance);db.flush()
        db.add_all([Signature(centre_id=centre.id,parent_id=None,signer_name='Parent confirmation',relationship='Caregiver',domain_type='attendance',domain_id=attendance.id,revision=1,purpose='parent_missing_sign_in_confirmation',signature_data='data:image/png;base64,recovered-in'),Signature(centre_id=centre.id,parent_id=None,signer_name='Parent confirmation',relationship='Caregiver',domain_type='attendance',domain_id=attendance.id,revision=1,purpose='parent_missing_sign_out_confirmation',signature_data='data:image/png;base64,recovered-out')]);db.commit()
        parent_client=TestClient(app);assert parent_client.post('/api/auth/parent/login',json={'login':'family','pin':'123456'}).status_code==200
        day=parent_client.get(f'/api/parent/children/{child.id}/day').json()['attendance'][0];assert day['sign_in_signature_purpose']=='parent_missing_sign_in_confirmation' and day['sign_out_signature_purpose']=='parent_missing_sign_out_confirmation'
        assert parent_client.get(f'/api/parent/attendance/{attendance.id}/signature?purpose=parent_missing_sign_in_confirmation').status_code==200
        exported=parent_client.get(f'/api/parent/children/{child.id}/export').text;assert 'Teacher sign-in / Parent confirmed' in exported and 'Teacher sign-out / Parent confirmed' in exported and 'Caregiver,Yes' in exported
        admin_client=TestClient(app);login(admin_client);activity=admin_client.get(f'/api/admin/activity?child_id={child.id}&type=attendance').json()['items'][0];assert activity['self_signed'] is False and activity['teacher']=='Sarah' and activity['sign_in_signature_purpose']=='parent_missing_sign_in_confirmation' and activity['sign_out_signature_purpose']=='parent_missing_sign_out_confirmation'
        assert admin_client.get(f'/api/admin/activity/attendance/{attendance.id}/signature?purpose=parent_missing_sign_in_confirmation').status_code==200
        unrelated=Parent(centre_id=centre.id,name='Other family',login='other-family',pin_hash=pwd.hash('654321'));db.add(unrelated);db.flush();db.add(ParentChild(parent_id=unrelated.id,child_id=absent.id));db.commit()
        unrelated_client=TestClient(app);assert unrelated_client.post('/api/auth/parent/login',json={'login':'other-family','pin':'654321'}).status_code==200;assert unrelated_client.get(f'/api/parent/attendance/{attendance.id}/signature?purpose=parent_missing_sign_in_confirmation').status_code==404
        other_client=TestClient(app);login(other_client,'other-admin');assert other_client.get(f'/api/admin/activity/attendance/{attendance.id}/signature?purpose=parent_missing_sign_in_confirmation').status_code==404
        assert audit_category(Audit(entity='attendance',action='parent_confirmed_missing_sign_in'))=='management' and audit_category(Audit(entity='attendance',action='future_signature_action'))=='security'
    finally:db.close()

def test_ancient_unsigned_completed_attendance_does_not_block_current_kiosk_use():
    db,centre,admin,office,teacher_account,other,other_admin,room,visit,staff,inactive,child,absent,parent=setup_020()
    try:
        db.add(Attendance(centre_id=centre.id,child_id=child.id,room_id=room.id,arrived_at=now()-timedelta(days=20,hours=2),departed_at=now()-timedelta(days=20,hours=1),recorded_by_staff_id=staff.id,source='classroom'));db.commit();kiosk=attendance_client(room)
        row=next(item for item in kiosk.get('/api/attendance/bootstrap').json()['children'] if item['id']==child.id);assert row['pending_attendance_confirmation'] is None
        assert kiosk.post('/api/attendance/kiosk',json={'child_id':child.id,'room_id':room.id,'action':'sign_in','relationship':'Mother','signature_data':'data:image/png;base64,today-arrival'}).status_code==200
    finally:db.close()
