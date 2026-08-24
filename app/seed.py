from sqlalchemy import select
from .auth import hash_password
from .config import settings
from .database import SessionLocal
from .models import ClientCompany, Contact, Project, ProjectCompany, ProjectContact, Property, Unit, User, UserRole, VerificationStatus
from .search import digits

def seed():
    db=SessionLocal()
    try:
        for email,password,role in [(settings.admin_email,settings.admin_password,UserRole.ADMIN),(settings.field_email,settings.field_password,UserRole.FIELD_USER)]:
            if not db.scalar(select(User).where(User.email==email.lower())): db.add(User(email=email.lower(),password_hash=hash_password(password),role=role))
        if not db.scalar(select(Project).where(Project.project_name=="155 Stuyvesant Ave Interior Renovation")):
            co=ClientCompany(company_name="ABC Development LLC",phone="212-555-0100",email="office@abcdev.example")
            prop=Property(street_address="155 Stuyvesant Ave",city="Brooklyn",borough="Brooklyn",state="NY",zip_code="11221")
            unit=Unit(property=prop,unit_number="1K"); project=Project(project_name="155 Stuyvesant Ave Interior Renovation",client_company=co,property=prop,unit=unit,project_type="Interior Renovation",status="Active")
            project.company_links.append(ProjectCompany(company=co,project_role="Client"))
            people=[("John","Smith","Client","917-555-1234","john@example.com"),("David","Chen","General Contractor","646-555-1234","david@abcconstruction.example"),("Mike","Brown","Superintendent","347-555-9876",None)]
            for first,last,role,phone,email in people:
                c=Contact(first_name=first,last_name=last,display_name=f"{first} {last}",role=role,phone=phone,phone_normalized=digits(phone),email=email,verification_status=VerificationStatus.VERIFIED)
                project.contact_links.append(ProjectContact(contact=c,project_role=role))
            db.add(project)
        db.commit()
    finally: db.close()
if __name__=="__main__": seed()
