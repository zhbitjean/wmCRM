import io, json
from sqlalchemy import select
from app.models import ClientCompany,Contact,Project,ProjectContact,Property,StagedRecord,Unit,VerificationStatus
from app.search import global_search
from conftest import login

def sample(db):
    company=ClientCompany(company_name="ABC Construction")
    prop=Property(street_address="155 Stuyvesant Ave",city="Brooklyn",borough="Brooklyn",state="NY",zip_code="11221")
    unit=Unit(property=prop,unit_number="1K")
    contact=Contact(first_name="David",last_name="Chen",display_name="David Chen",nickname="Gongji",phone="(917) 555-1234",phone_normalized="9175551234",email="david@gmail.com",company=company)
    project=Project(project_name="Interior Renovation",client_company=company,property=prop,unit=unit)
    project.contact_links.append(ProjectContact(contact=contact,project_role="General Contractor")); db.add(project); db.commit(); return company,prop,unit,contact,project
def test_relationships(db):
    company,prop,unit,contact,project=sample(db)
    assert contact in company.contacts and project in company.projects
    assert unit in prop.units and project.unit is unit
    assert project.contact_links[0].contact is contact
    assert project.contact_links[0].project_role=="General Contractor"
def test_global_search_all_key_fields(db):
    *_,project=sample(db)
    for query in ["155 Stuy","1K","David","gongji","ABC Construction","917-555-1234","gmail.com","Interior Reno"]:
        assert project in global_search(db,query), query
def test_field_user_cannot_write(client):
    login(client,"field@test.com")
    assert client.get("/?q=155").status_code==200
    assert client.post("/admin/companies",data={"company_name":"Nope"}).status_code==403
def test_csv_review_and_approval(client,db):
    login(client)
    csv=b"entity_type,first_name,last_name,phone,email,role\ncontact,Jane,Doe,718-555-9000,jane@example.com,Owner\n"
    assert client.post("/admin/import",files={"file":("people.csv",io.BytesIO(csv),"text/csv")}).status_code==200
    db.expire_all(); staged=db.scalar(select(StagedRecord)); assert staged.status==VerificationStatus.PENDING
    assert client.post(f"/admin/staged/{staged.id}/approve").status_code==200
    db.expire_all(); staged=db.get(StagedRecord,staged.id); jane=db.scalar(select(Contact).where(Contact.email=="jane@example.com"))
    assert staged.status==VerificationStatus.VERIFIED and jane.verification_status==VerificationStatus.VERIFIED
