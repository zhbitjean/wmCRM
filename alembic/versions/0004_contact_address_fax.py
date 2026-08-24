"""add contact address and fax"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("contacts", sa.Column("fax", sa.String(length=50), nullable=True))
    op.add_column("contacts", sa.Column("address", sa.String(length=500), nullable=True))

def downgrade():
    op.drop_column("contacts", "address")
    op.drop_column("contacts", "fax")
