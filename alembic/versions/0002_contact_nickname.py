"""add searchable contact nickname"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("contacts", sa.Column("nickname", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_contacts_nickname"), "contacts", ["nickname"], unique=False)

def downgrade():
    op.drop_index(op.f("ix_contacts_nickname"), table_name="contacts")
    op.drop_column("contacts", "nickname")
