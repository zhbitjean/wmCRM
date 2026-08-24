import io, json
from sqlalchemy import select
from app.models import ClientCompany,Contact,Project,ProjectContact,Property,StagedRecord,Unit,VerificationStatus
from app.search import directory_search, global_search
from app.importers import map_client_row
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
    contacts,companies=directory_search(db,"gongji")
    assert any(contact.nickname=="Gongji" for contact in contacts)
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

def test_current_client_row_mapping_and_bundle_approval(client,db):
    mapped=map_client_row({"Name":"Joseph Aghelian","Nickname":"Gongji","Company":"PSA Properties","Address":"79 Water Mill Lane, Great Neck, NY 11021","Office Phone":"(516) 216-1360","Fax":"(516) 216-1363","Cell Phone":"-","Notes":"Big Guy","Email":" joseph@psaproperties.com "})
    assert mapped["nickname"]=="Gongji" and mapped["phone"]=="(516) 216-1360" and mapped["email"]=="joseph@psaproperties.com"
    staged=StagedRecord(entity_type="client_bundle",payload_json=json.dumps(mapped),source_type="EXCEL",source_reference="WM Client list.xlsx / current client list")
    db.add(staged); db.commit(); login(client)
    assert client.post(f"/admin/staged/{staged.id}/approve").status_code==200
    db.expire_all(); joseph=db.scalar(select(Contact).where(Contact.nickname=="Gongji")); company=db.scalar(select(ClientCompany).where(ClientCompany.company_name=="PSA Properties"))
    assert joseph and joseph.company_id==company.id
    assert company.address.startswith("79 Water Mill") and company.fax=="(516) 216-1363"
    assert joseph.address.startswith("79 Water Mill") and joseph.fax=="(516) 216-1363"
