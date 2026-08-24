"""add duplicate candidates to staged records"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("staged_records") as batch:
        batch.add_column(sa.Column("duplicate_contact_id",sa.Integer(),nullable=True))
        batch.add_column(sa.Column("duplicate_company_id",sa.Integer(),nullable=True))
        batch.add_column(sa.Column("duplicate_reasons",sa.Text(),nullable=True))
        batch.create_foreign_key("fk_staged_duplicate_contact","contacts",["duplicate_contact_id"],["id"])
        batch.create_foreign_key("fk_staged_duplicate_company","client_companies",["duplicate_company_id"],["id"])

def downgrade():
    with op.batch_alter_table("staged_records") as batch:
        batch.drop_constraint("fk_staged_duplicate_company",type_="foreignkey")
        batch.drop_constraint("fk_staged_duplicate_contact",type_="foreignkey")
        batch.drop_column("duplicate_reasons")
        batch.drop_column("duplicate_company_id")
        batch.drop_column("duplicate_contact_id")
