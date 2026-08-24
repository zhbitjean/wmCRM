"""add project company roles"""
from alembic import op
import sqlalchemy as sa

revision="0007"
down_revision="0006"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("project_companies",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("project_id",sa.Integer(),sa.ForeignKey("projects.id"),nullable=False),sa.Column("company_id",sa.Integer(),sa.ForeignKey("client_companies.id"),nullable=False),sa.Column("project_role",sa.String(length=100),nullable=False),sa.Column("notes",sa.Text(),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_by",sa.String(length=255),nullable=True),sa.Column("updated_by",sa.String(length=255),nullable=True),sa.UniqueConstraint("project_id","company_id","project_role",name="uq_project_company_role"))
    op.execute(sa.text("INSERT INTO project_companies (project_id,company_id,project_role,created_at,updated_at) SELECT id,client_company_id,'Client',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM projects WHERE client_company_id IS NOT NULL"))

def downgrade():
    op.drop_table("project_companies")
