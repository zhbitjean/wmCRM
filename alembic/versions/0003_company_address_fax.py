"""add company address and fax"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("client_companies", sa.Column("fax", sa.String(length=50), nullable=True))
    op.add_column("client_companies", sa.Column("address", sa.String(length=500), nullable=True))

def downgrade():
    op.drop_column("client_companies", "address")
    op.drop_column("client_companies", "fax")
