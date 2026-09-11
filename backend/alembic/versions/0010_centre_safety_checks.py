"""Add immutable per-room Centre Safety Check snapshots."""
from alembic import op
import sqlalchemy as sa

revision='0010'
down_revision='0009'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table(
        'centre_safety_checks',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('centre_id',sa.String(36),sa.ForeignKey('centres.id'),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('completed_at',sa.DateTime(timezone=True)),
        sa.Column('staff_id',sa.String(36),sa.ForeignKey('staff.id'),nullable=False),
        sa.Column('account_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),
        sa.Column('status',sa.String(20),nullable=False,server_default='open')
    )
    op.create_index('ix_centre_safety_checks_centre_id','centre_safety_checks',['centre_id'])
    op.create_table(
        'centre_safety_check_rooms',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('safety_check_id',sa.String(36),sa.ForeignKey('centre_safety_checks.id'),nullable=False),
        sa.Column('centre_id',sa.String(36),sa.ForeignKey('centres.id'),nullable=False),
        sa.Column('room_id',sa.String(36),sa.ForeignKey('rooms.id'),nullable=False),
        sa.Column('room_name',sa.String(100),nullable=False),
        sa.Column('expected_count',sa.Integer(),nullable=False),
        sa.Column('observed_count',sa.Integer(),nullable=False),
        sa.Column('expected_children',sa.JSON(),nullable=False),
        sa.Column('checked_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('staff_id',sa.String(36),sa.ForeignKey('staff.id'),nullable=False),
        sa.Column('note',sa.Text()),
        sa.UniqueConstraint('safety_check_id','room_id')
    )
    op.create_index('ix_centre_safety_check_rooms_safety_check_id','centre_safety_check_rooms',['safety_check_id'])
    op.create_index('ix_centre_safety_check_rooms_centre_id','centre_safety_check_rooms',['centre_id'])

def downgrade():
    op.drop_index('ix_centre_safety_check_rooms_centre_id',table_name='centre_safety_check_rooms')
    op.drop_index('ix_centre_safety_check_rooms_safety_check_id',table_name='centre_safety_check_rooms')
    op.drop_table('centre_safety_check_rooms')
    op.drop_index('ix_centre_safety_checks_centre_id',table_name='centre_safety_checks')
    op.drop_table('centre_safety_checks')
