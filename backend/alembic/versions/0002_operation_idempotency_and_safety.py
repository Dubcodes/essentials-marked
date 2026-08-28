"""Add durable operation IDs and high-consequence uniqueness guards."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'domain_operations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('centre_id', sa.String(36), sa.ForeignKey('centres.id'), nullable=False),
        sa.Column('domain', sa.String(40), nullable=False),
        sa.Column('client_operation_id', sa.String(80), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('centre_id', 'domain', 'client_operation_id', name='uq_domain_operation'),
    )
    op.create_index('ix_domain_operations_centre_id', 'domain_operations', ['centre_id'])
    op.add_column('medication_administrations', sa.Column('client_operation_id', sa.String(80), nullable=True))
    op.create_index('uq_medication_administration_operation', 'medication_administrations', ['centre_id', 'client_operation_id'], unique=True)
    op.create_index('uq_active_medication_receipt', 'medication_receipts', ['authority_id'], unique=True, sqlite_where=sa.text('returned_at IS NULL'), postgresql_where=sa.text('returned_at IS NULL'))
    op.add_column('incidents', sa.Column('client_draft_id', sa.String(80), nullable=True))
    op.add_column('incidents', sa.Column('finalise_operation_id', sa.String(80), nullable=True))
    op.create_index('uq_incident_draft_operation', 'incidents', ['centre_id', 'client_draft_id'], unique=True)
    op.create_index('uq_incident_finalise_operation', 'incidents', ['centre_id', 'finalise_operation_id'], unique=True)


def downgrade():
    op.drop_index('uq_incident_finalise_operation', table_name='incidents')
    op.drop_index('uq_incident_draft_operation', table_name='incidents')
    op.drop_column('incidents', 'finalise_operation_id')
    op.drop_column('incidents', 'client_draft_id')
    op.drop_index('uq_active_medication_receipt', table_name='medication_receipts')
    op.drop_index('uq_medication_administration_operation', table_name='medication_administrations')
    op.drop_column('medication_administrations', 'client_operation_id')
    op.drop_index('ix_domain_operations_centre_id', table_name='domain_operations')
    op.drop_table('domain_operations')
