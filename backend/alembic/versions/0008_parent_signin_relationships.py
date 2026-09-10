"""Add family-scoped parent sign-in relationship options."""
from alembic import op
import sqlalchemy as sa
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('parent_relationship_options',sa.Column('id',sa.String(36),primary_key=True),sa.Column('centre_id',sa.String(36),sa.ForeignKey('centres.id'),nullable=False),sa.Column('parent_id',sa.String(36),sa.ForeignKey('parents.id'),nullable=False),sa.Column('label',sa.String(100),nullable=False),sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('parent_id','label'))
    op.create_index('ix_parent_relationship_options_centre_id','parent_relationship_options',['centre_id'])
def downgrade():
    op.drop_index('ix_parent_relationship_options_centre_id',table_name='parent_relationship_options');op.drop_table('parent_relationship_options')
