"""Close replay, visit-state, and medication-date integrity gaps."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('attendance') as batch:
        batch.add_column(sa.Column('last_visit_room_id', sa.String(36), sa.ForeignKey('rooms.id', name='fk_attendance_last_visit_room'), nullable=True))
    op.add_column('domain_operations', sa.Column('request_fingerprint', sa.String(64), nullable=True))
    op.add_column('medication_administrations', sa.Column('request_fingerprint', sa.String(64), nullable=True))
    op.add_column('incidents', sa.Column('finalise_request_fingerprint', sa.String(64), nullable=True))

    op.add_column('medication_authorities', sa.Column('starts_on_date', sa.Date(), nullable=True))
    op.add_column('medication_authorities', sa.Column('ends_on_date', sa.Date(), nullable=True))
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('UPDATE medication_authorities SET starts_on_date = starts_on::date WHERE starts_on IS NOT NULL')
        op.execute('UPDATE medication_authorities SET ends_on_date = ends_on::date WHERE ends_on IS NOT NULL')
    else:
        op.execute('UPDATE medication_authorities SET starts_on_date = starts_on WHERE starts_on IS NOT NULL')
        op.execute('UPDATE medication_authorities SET ends_on_date = ends_on WHERE ends_on IS NOT NULL')
    with op.batch_alter_table('medication_authorities') as batch:
        batch.drop_column('starts_on')
        batch.drop_column('ends_on')
        batch.alter_column('starts_on_date', new_column_name='starts_on', existing_type=sa.Date())
        batch.alter_column('ends_on_date', new_column_name='ends_on', existing_type=sa.Date())


def downgrade():
    op.add_column('medication_authorities', sa.Column('starts_on_text', sa.String(10), nullable=True))
    op.add_column('medication_authorities', sa.Column('ends_on_text', sa.String(10), nullable=True))
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("UPDATE medication_authorities SET starts_on_text = starts_on::text WHERE starts_on IS NOT NULL")
        op.execute("UPDATE medication_authorities SET ends_on_text = ends_on::text WHERE ends_on IS NOT NULL")
    else:
        op.execute('UPDATE medication_authorities SET starts_on_text = starts_on WHERE starts_on IS NOT NULL')
        op.execute('UPDATE medication_authorities SET ends_on_text = ends_on WHERE ends_on IS NOT NULL')
    with op.batch_alter_table('medication_authorities') as batch:
        batch.drop_column('starts_on')
        batch.drop_column('ends_on')
        batch.alter_column('starts_on_text', new_column_name='starts_on', existing_type=sa.String(10))
        batch.alter_column('ends_on_text', new_column_name='ends_on', existing_type=sa.String(10))
    op.drop_column('incidents', 'finalise_request_fingerprint')
    op.drop_column('medication_administrations', 'request_fingerprint')
    op.drop_column('domain_operations', 'request_fingerprint')
    with op.batch_alter_table('attendance') as batch:
        batch.drop_column('last_visit_room_id')
