import re
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session, joinedload
from .models import ClientCompany, Contact, Project, ProjectContact, Property, Unit

def digits(value: str): return re.sub(r"\D", "", value or "")
def global_search(db: Session, query: str):
    q=query.strip(); pattern=f"%{q}%"; phone=digits(q)
    filters=[Project.project_name.ilike(pattern),Property.street_address.ilike(pattern),Property.address_line_2.ilike(pattern),Property.city.ilike(pattern),Property.borough.ilike(pattern),Property.building_name.ilike(pattern),Unit.unit_number.ilike(pattern),ClientCompany.company_name.ilike(pattern),ClientCompany.alternate_name.ilike(pattern),ClientCompany.address.ilike(pattern),ClientCompany.borough.ilike(pattern),Contact.display_name.ilike(pattern),Contact.nickname.ilike(pattern),Contact.email.ilike(pattern),Contact.phone.ilike(pattern)]
    if phone: filters.append(Contact.phone_normalized.ilike(f"%{phone}%"))
    stmt=(select(Project).outerjoin(Property).outerjoin(Unit,Project.unit_id==Unit.id).outerjoin(ClientCompany).outerjoin(ProjectContact).outerjoin(Contact).where(or_(*filters)).options(joinedload(Project.property),joinedload(Project.unit),joinedload(Project.client_company),joinedload(Project.contact_links).joinedload(ProjectContact.contact)).distinct())
    return db.execute(stmt).unique().scalars().all()

def directory_search(db: Session, query: str):
    q=query.strip(); pattern=f"%{q}%"; phone=digits(q)
    contact_filters=[Contact.display_name.ilike(pattern),Contact.nickname.ilike(pattern),Contact.email.ilike(pattern),Contact.phone.ilike(pattern),Contact.address.ilike(pattern),Contact.borough.ilike(pattern)]
    if phone: contact_filters.append(Contact.phone_normalized.ilike(f"%{phone}%"))
    contacts=db.execute(select(Contact).outerjoin(ClientCompany).where(or_(*contact_filters,ClientCompany.company_name.ilike(pattern))).options(joinedload(Contact.company),joinedload(Contact.project_links).joinedload(ProjectContact.project)).distinct()).unique().scalars().all()
    companies=db.execute(select(ClientCompany).where(or_(ClientCompany.company_name.ilike(pattern),ClientCompany.alternate_name.ilike(pattern),ClientCompany.phone.ilike(pattern),ClientCompany.email.ilike(pattern),ClientCompany.address.ilike(pattern),ClientCompany.borough.ilike(pattern))).options(joinedload(ClientCompany.contacts),joinedload(ClientCompany.projects)).distinct()).unique().scalars().all()
    return contacts,companies
