"""Add Emergency Roll print orientation and name-size settings."""
from alembic import op
import sqlalchemy as sa

revision='0011'
down_revision='0010'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('centres',sa.Column('emergency_orientation',sa.String(20),nullable=False,server_default='portrait'))
    op.add_column('centres',sa.Column('emergency_name_size',sa.String(20),nullable=False,server_default='standard'))

def downgrade():
    op.drop_column('centres','emergency_name_size')
    op.drop_column('centres','emergency_orientation')
