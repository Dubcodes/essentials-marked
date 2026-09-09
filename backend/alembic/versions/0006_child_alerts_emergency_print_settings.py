"""Add child supply alerts and centre emergency-print preferences."""
from alembic import op
import sqlalchemy as sa

revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('centres',sa.Column('emergency_columns',sa.Integer(),nullable=False,server_default='3'))
    op.add_column('centres',sa.Column('emergency_sort',sa.String(30),nullable=False,server_default='room_then_name'))
    op.add_column('centres',sa.Column('emergency_show_room',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_table('child_alerts',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('centre_id',sa.String(36),sa.ForeignKey('centres.id'),nullable=False),
        sa.Column('child_id',sa.String(36),sa.ForeignKey('children.id'),nullable=False),sa.Column('type',sa.String(50),nullable=False),
        sa.Column('event_id',sa.String(36),sa.ForeignKey('events.id'),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_by_staff_id',sa.String(36),sa.ForeignKey('staff.id'),nullable=True),sa.Column('touched_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('resolved_at',sa.DateTime(timezone=True),nullable=True),sa.Column('resolved_by_staff_id',sa.String(36),sa.ForeignKey('staff.id'),nullable=True))
    op.create_index('ix_open_child_alert','child_alerts',['centre_id','child_id','type','resolved_at'])

def downgrade():
    op.drop_index('ix_open_child_alert',table_name='child_alerts');op.drop_table('child_alerts')
    op.drop_column('centres','emergency_show_room');op.drop_column('centres','emergency_sort');op.drop_column('centres','emergency_columns')
