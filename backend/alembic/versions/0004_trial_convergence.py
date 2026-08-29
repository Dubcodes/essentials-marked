"""Add operational history, pairing metadata, branding, and parent requests."""
from alembic import op
import sqlalchemy as sa

revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('centres',sa.Column('display_name',sa.String(200),nullable=True))
    op.add_column('centres',sa.Column('secondary_text',sa.String(240),nullable=True))
    op.add_column('centres',sa.Column('logo_path',sa.String(300),nullable=True))
    with op.batch_alter_table('attendance') as batch:
        batch.add_column(sa.Column('recorded_by_staff_id',sa.String(36),nullable=True))
        batch.add_column(sa.Column('device_id',sa.String(36),nullable=True))
        batch.create_foreign_key('fk_attendance_staff','staff',['recorded_by_staff_id'],['id'])
        batch.create_foreign_key('fk_attendance_device','devices',['device_id'],['id'])
    with op.batch_alter_table('pairings') as batch:
        batch.add_column(sa.Column('label',sa.String(120),nullable=False,server_default='Classroom tablet'))
        batch.add_column(sa.Column('device_id',sa.String(36),nullable=True))
        batch.create_foreign_key('fk_pairings_device','devices',['device_id'],['id'])
    op.create_table('room_visits',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('centre_id',sa.String(36),sa.ForeignKey('centres.id'),nullable=False,index=True),
        sa.Column('attendance_id',sa.String(36),sa.ForeignKey('attendance.id'),nullable=False,index=True),
        sa.Column('child_id',sa.String(36),sa.ForeignKey('children.id'),nullable=False,index=True),
        sa.Column('room_id',sa.String(36),sa.ForeignKey('rooms.id'),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ended_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('started_by_staff_id',sa.String(36),sa.ForeignKey('staff.id'),nullable=True),
        sa.Column('ended_by_staff_id',sa.String(36),sa.ForeignKey('staff.id'),nullable=True),
        sa.Column('device_id',sa.String(36),sa.ForeignKey('devices.id'),nullable=True))
    op.create_table('parent_data_requests',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('centre_id',sa.String(36),sa.ForeignKey('centres.id'),nullable=False,index=True),
        sa.Column('parent_id',sa.String(36),sa.ForeignKey('parents.id'),nullable=False,index=True),
        sa.Column('child_id',sa.String(36),sa.ForeignKey('children.id'),nullable=False,index=True),
        sa.Column('start_date',sa.Date(),nullable=False),
        sa.Column('end_date',sa.Date(),nullable=False),
        sa.Column('note',sa.Text(),nullable=True),
        sa.Column('status',sa.String(20),nullable=False,server_default='new'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('handled_by_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=True))

def downgrade():
    op.drop_table('parent_data_requests')
    op.drop_table('room_visits')
    with op.batch_alter_table('pairings') as batch:
        batch.drop_constraint('fk_pairings_device',type_='foreignkey')
        batch.drop_column('device_id')
        batch.drop_column('label')
    with op.batch_alter_table('attendance') as batch:
        batch.drop_constraint('fk_attendance_device',type_='foreignkey')
        batch.drop_constraint('fk_attendance_staff',type_='foreignkey')
        batch.drop_column('device_id')
        batch.drop_column('recorded_by_staff_id')
    op.drop_column('centres','logo_path')
    op.drop_column('centres','secondary_text')
    op.drop_column('centres','display_name')
