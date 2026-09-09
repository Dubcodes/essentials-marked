"""Add child middle name for the 0.1.4 operational UI."""
from alembic import op
import sqlalchemy as sa

revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('children',sa.Column('middle_name',sa.String(100),nullable=True))
    op.add_column('attendance',sa.Column('source',sa.String(30),nullable=False,server_default='classroom'))
    op.add_column('attendance',sa.Column('late_sign_in',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('attendance',sa.Column('circumstance',sa.String(240),nullable=True))
    op.add_column('attendance',sa.Column('signer_name',sa.String(200),nullable=True))
    op.add_column('attendance',sa.Column('signer_relationship',sa.String(100),nullable=True))

def downgrade():
    op.drop_column('attendance','signer_relationship')
    op.drop_column('attendance','signer_name')
    op.drop_column('attendance','circumstance')
    op.drop_column('attendance','late_sign_in')
    op.drop_column('attendance','source')
    op.drop_column('children','middle_name')
