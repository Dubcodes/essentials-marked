"""Isolated PostgreSQL 15 release probe; invoked only by test_postgres_integration."""
import os,uuid
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic import command

base_url=os.environ['POSTGRES_TEST_URL'];schema='essentials_trial_'+uuid.uuid4().hex;db=None
admin_engine=create_engine(base_url,isolation_level='AUTOCOMMIT')
with admin_engine.connect() as connection:connection.execute(text(f'CREATE SCHEMA "{schema}"'))
url=make_url(base_url);query=dict(url.query);query['options']=f'-csearch_path={schema}';schema_url=str(url.set(query=query));os.environ['DATABASE_URL']=schema_url;os.environ['DEMO_SEED']='false'
try:
    config=Config('alembic.ini');config.set_main_option('sqlalchemy.url',schema_url.replace('%','%%'))
    command.upgrade(config,'0006')
    with admin_engine.connect() as connection:
        connection.execute(text(f"INSERT INTO \"{schema}\".centres (id,name) VALUES ('upgrade-centre','Existing centre')"))
        connection.execute(text(f"INSERT INTO \"{schema}\".accounts (id,centre_id,email,password_hash) VALUES ('upgrade-account','upgrade-centre','existing@example.test','hash')"))
        connection.execute(text(f"INSERT INTO \"{schema}\".devices (id,centre_id,label,created_at,last_active_at) VALUES ('upgrade-device','upgrade-centre','Existing tablet',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text(f"INSERT INTO \"{schema}\".pairings (id,centre_id,label,token_hash,challenge,expires_at) VALUES ('upgrade-pairing','upgrade-centre','Existing pairing','hash','123456',CURRENT_TIMESTAMP)"))
        connection.commit()
    command.upgrade(config,'0008')
    with admin_engine.connect() as connection:
        row=connection.execute(text(f'SELECT login_id,email FROM "{schema}".accounts WHERE id=\'upgrade-account\'')).one()
        assert row.login_id=='existing@example.test' and row.email=='existing@example.test'
        connection.execute(text(f'UPDATE "{schema}".accounts SET email=NULL WHERE id=\'upgrade-account\''))
        modes=connection.execute(text(f'SELECT d.mode,p.mode FROM "{schema}".devices d CROSS JOIN "{schema}".pairings p WHERE d.id=\'upgrade-device\' AND p.id=\'upgrade-pairing\'')).one()
        assert tuple(modes)==('classroom','classroom')
        connection.execute(text(f"INSERT INTO \"{schema}\".parents (id,centre_id,name,login,pin_hash) VALUES ('upgrade-parent','upgrade-centre','Existing parent','existing-parent','hash')"))
        connection.execute(text(f"INSERT INTO \"{schema}\".parent_relationship_options (id,centre_id,parent_id,label,created_at) VALUES ('upgrade-relationship','upgrade-centre','upgrade-parent','Grandparent',CURRENT_TIMESTAMP)"))
        connection.commit()
    command.upgrade(config,'head')
    with admin_engine.connect() as connection:
        assert connection.execute(text(f'SELECT attendance_relationship_required FROM "{schema}".centres WHERE id=\'upgrade-centre\'')).scalar_one() is True
        print_settings=connection.execute(text(f'SELECT emergency_orientation,emergency_name_size FROM "{schema}".centres WHERE id=\'upgrade-centre\'')).one()
        assert tuple(print_settings)==('portrait','standard')
        assert connection.execute(text(f'SELECT count(*) FROM "{schema}".parent_relationship_options WHERE id=\'upgrade-relationship\'')).scalar_one()==1
    inspector=inspect(admin_engine)
    check_tables={'centre_safety_checks','centre_safety_check_rooms'}
    assert check_tables.issubset(set(inspector.get_table_names(schema=schema)))
    assert {'ix_centre_safety_checks_centre_id'}.issubset({item['name'] for item in inspector.get_indexes('centre_safety_checks',schema=schema)})
    assert {'ix_centre_safety_check_rooms_safety_check_id','ix_centre_safety_check_rooms_centre_id'}.issubset({item['name'] for item in inspector.get_indexes('centre_safety_check_rooms',schema=schema)})
    assert len(inspector.get_foreign_keys('centre_safety_checks',schema=schema))==3
    assert len(inspector.get_foreign_keys('centre_safety_check_rooms',schema=schema))==4
    assert any(set(item.get('column_names') or ())=={'safety_check_id','room_id'} for item in inspector.get_unique_constraints('centre_safety_check_rooms',schema=schema))
    from fastapi.testclient import TestClient
    from app.main import app,pwd
    from app.db import SessionLocal
    from app.models import Centre,Account,Room,Staff,Child,Event,RoomVisit,Incident
    db=SessionLocal();centre=Centre(name='Postgres Trial');db.add(centre);db.flush();account=Account(centre_id=centre.id,login_id='postgres@test.local',email='postgres@test.local',password_hash=pwd.hash('secret'));room=Room(centre_id=centre.id,name='Room');visit=Room(centre_id=centre.id,name='Visit');staff=Staff(centre_id=centre.id,first_name='Test',last_name='Teacher',pin_hash=pwd.hash('1234'));child=Child(centre_id=centre.id,room_id=room.id,first_name='Child');db.add_all([account,room,visit,staff,child]);db.commit()
    client=TestClient(app);assert client.post('/api/auth/admin/login',json={'email':'postgres@test.local','password':'secret'}).status_code==200;pair=client.post('/api/admin/pairings',json={'room_id':room.id,'label':'Postgres tablet'}).json();assert client.post('/api/device/pair',json={'token':pair['token'],'challenge':pair['challenge']}).status_code==200
    ordinary={'client_id':'postgres-ordinary-001','child_ids':[child.id],'type':'sunscreen','room_id':room.id,'performed_by_id':staff.id,'data':{'application':'exposed skin'}};assert client.post('/api/classroom/events',json=ordinary).status_code==200;assert client.post('/api/classroom/events',json=ordinary).json()['idempotent'];assert client.post('/api/classroom/events',json={**ordinary,'data':{'application':'changed'}}).status_code==409
    food={'client_operation_id':'postgres-food-batch-01','room_id':room.id,'staff_id':staff.id,'meal':'Lunch','rows':[{'child_id':child.id,'food':'Pasta','servings':[1]}]};assert client.post('/api/classroom/food-batch',json=food).status_code==200;assert client.post('/api/classroom/food-batch',json=food).json()['idempotent']
    presence={'child_id':child.id,'staff_id':staff.id};assert client.post('/api/classroom/presence',json={**presence,'room_id':room.id,'action':'arrive'}).status_code==200;assert client.post('/api/classroom/presence',json={**presence,'room_id':visit.id,'action':'visit'}).status_code==200;assert client.post('/api/classroom/presence',json={**presence,'room_id':visit.id,'action':'end_visit'}).status_code==200
    incident={'client_draft_id':'postgres-incident-draft','child_id':child.id,'room_id':room.id,'staff_id':staff.id,'incident_type':'bump','actions':[{'description':'comforted'}]};created=client.post('/api/classroom/incidents',json=incident);assert created.status_code==200;final={**incident,'incident_id':created.json()['id'],'finalise':True,'finalise_operation_id':'postgres-incident-final','staff_pin':'1234'};assert client.post('/api/classroom/incidents',json=final).status_code==200
    assert db.query(Event).count()==3 and db.query(RoomVisit).count()==1 and db.query(Incident).filter_by(status='finalised').count()==1
finally:
    if db is not None:db.close()
    try:
        from app.db import engine
        engine.dispose()
    except Exception:pass
    with admin_engine.connect() as connection:connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin_engine.dispose()
