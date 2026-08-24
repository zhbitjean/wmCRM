"""add searchable boroughs to contacts and companies"""
from alembic import op
import sqlalchemy as sa

revision="0006"
down_revision="0005"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("contacts",sa.Column("borough",sa.String(length=50),nullable=True))
    op.add_column("client_companies",sa.Column("borough",sa.String(length=50),nullable=True))
    op.create_index(op.f("ix_contacts_borough"),"contacts",["borough"],unique=False)
    op.create_index(op.f("ix_client_companies_borough"),"client_companies",["borough"],unique=False)
    queens=("queens","flushing","glendale","richmond hill","kew gardens","far rockaway","long island city","astoria","woodside","sunnyside","jackson heights","elmhurst","rego park","forest hills","jamaica","bayside","fresh meadows","college point","whitestone","corona","maspeth","middle village","ridgewood","ozone park","howard beach","woodhaven")
    for table in ("contacts","client_companies"):
        condition=" OR ".join(f"lower(address) LIKE '%{term}%'" for term in queens)
        op.execute(sa.text(f"UPDATE {table} SET borough='Queens' WHERE borough IS NULL AND address IS NOT NULL AND ({condition})"))
        op.execute(sa.text(f"UPDATE {table} SET borough='Brooklyn' WHERE borough IS NULL AND lower(address) LIKE '%brooklyn%'"))
        op.execute(sa.text(f"UPDATE {table} SET borough='Bronx' WHERE borough IS NULL AND lower(address) LIKE '%bronx%'"))
        op.execute(sa.text(f"UPDATE {table} SET borough='Staten Island' WHERE borough IS NULL AND lower(address) LIKE '%staten island%'"))
        op.execute(sa.text(f"UPDATE {table} SET borough='Manhattan' WHERE borough IS NULL AND (lower(address) LIKE '%manhattan%' OR lower(address) LIKE '%new york, ny%' OR lower(address) LIKE '%new york ny%')"))

def downgrade():
    op.drop_index(op.f("ix_client_companies_borough"),table_name="client_companies")
    op.drop_index(op.f("ix_contacts_borough"),table_name="contacts")
    op.drop_column("client_companies","borough")
    op.drop_column("contacts","borough")
