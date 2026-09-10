"""Add attendance-device capability and account login IDs."""
from alembic import op
import sqlalchemy as sa

revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('devices',sa.Column('mode',sa.String(20),nullable=False,server_default='classroom'))
    op.add_column('pairings',sa.Column('mode',sa.String(20),nullable=False,server_default='classroom'))
    op.add_column('accounts',sa.Column('login_id',sa.String(255),nullable=True))
    op.execute("UPDATE accounts SET login_id=email WHERE login_id IS NULL")
    # SQLite cannot alter column nullability in place; batch mode preserves
    # the deployed data while rebuilding only this small table where needed.
    with op.batch_alter_table('accounts') as batch:
        batch.alter_column('login_id',existing_type=sa.String(255),nullable=False)
        batch.create_unique_constraint('uq_accounts_login_id',['login_id'])
        batch.alter_column('email',existing_type=sa.String(255),nullable=True)

def downgrade():
    with op.batch_alter_table('accounts') as batch:
        batch.drop_constraint('uq_accounts_login_id',type_='unique');batch.drop_column('login_id')
    op.drop_column('pairings','mode');op.drop_column('devices','mode')
