"""Add the Parent sign-in relationship requirement setting."""
from alembic import op
import sqlalchemy as sa

revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('centres',sa.Column('attendance_relationship_required',sa.Boolean(),nullable=False,server_default=sa.true()))

def downgrade():
    op.drop_column('centres','attendance_relationship_required')
