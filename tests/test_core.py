import io, json
from sqlalchemy import select
from app.models import ClientCompany,Contact,Project,ProjectCompany,ProjectContact,Property,StagedRecord,Unit,VerificationStatus
from app.search import directory_search, global_search
from app.importers import map_client_row
from app.duplicates import annotate_duplicate, find_duplicate
from app.geography import infer_nyc_borough
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
    assert client.get("/contacts/new").status_code==403

def test_admin_can_add_contact_directly(client,db):
    login(client)
    assert client.get("/contacts/new").status_code==200
    response=client.post("/contacts/new",data={"first_name":"Dave","last_name":"Miller","nickname":"D","role":"Site Contact","phone":"212-555-0199","email":"dave@example.com","address":"2600 Amsterdam Ave, New York, NY","borough":"Manhattan","notes":"Secondary person in charge"},follow_redirects=False)
    assert response.status_code==303 and response.headers["location"].startswith("/contacts/")
    db.expire_all(); dave=db.scalar(select(Contact).where(Contact.email=="dave@example.com"))
    assert dave and dave.display_name=="Dave Miller" and dave.borough=="Manhattan" and dave.verification_status==VerificationStatus.VERIFIED

def test_queens_borough_inference_and_lookup(db):
    assert infer_nyc_borough("71-16 Myrtle Ave, Glendale, NY 11385")=="Queens"
    assert infer_nyc_borough("138-16 57 Rd, Flushing, NY 11355")=="Queens"
    contact=Contact(first_name="Queens",last_name="Contact",display_name="Queens Contact",address="86-25 Lefferts Blvd, Richmond Hill, NY",borough=infer_nyc_borough("86-25 Lefferts Blvd, Richmond Hill, NY"))
    db.add(contact); db.commit(); contacts,_=directory_search(db,"queens")
    assert contact in contacts
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

def test_duplicate_detection_and_manual_merge(client,db):
    company=ClientCompany(company_name="ABC Construction LLC")
    existing=Contact(first_name="Mike",last_name="Chen",display_name="Mike Chen",phone="917-555-1234",phone_normalized="9175551234",company=company)
    db.add(existing); db.commit()
    payload={"display_name":"Michael Chen","first_name":"Michael","last_name":"Chen","company_name":"ABC Construction","phone":"(917) 555-1234","email":"mike@example.com","role":"GC","notes":"Met at site"}
    record=StagedRecord(entity_type="client_bundle",payload_json=json.dumps(payload),source_type="EXCEL",source_reference="intake.xlsx")
    annotate_duplicate(db,record,payload); db.add(record); db.commit()
    assert record.duplicate_contact_id==existing.id
    assert "Exact normalized phone match" in json.loads(record.duplicate_reasons)
    login(client); assert client.post(f"/admin/staged/{record.id}/merge").status_code==200
    db.expire_all(); existing=db.get(Contact,existing.id); record=db.get(StagedRecord,record.id)
    assert existing.display_name=="Mike Chen"  # merge preserves populated values
    assert existing.email=="mike@example.com" and existing.notes=="Met at site"
    assert record.status==VerificationStatus.VERIFIED and "Merged" in record.review_notes

def test_project_first_creation_and_role_assignment(client,db):
    company=ClientCompany(company_name="XYZ Construction")
    contact=Contact(first_name="Dave",last_name="Miller",display_name="Dave Miller",phone="212-555-0101",phone_normalized="2125550101")
    db.add_all([company,contact]); db.commit(); login(client)
    response=client.post("/projects/new",data={"project_name":"Amsterdam Renovation","street_address":"2600 Amsterdam Ave","city":"New York","state":"NY","zip_code":"10040","borough":"Manhattan","project_type":"Renovation","status":"Active","client_company_id":company.id},follow_redirects=False)
    assert response.status_code==303
    db.expire_all(); project=db.scalar(select(Project).where(Project.project_name=="Amsterdam Renovation"))
    assert project.property.street_address=="2600 Amsterdam Ave" and project.property.borough=="Manhattan"
    assert db.scalar(select(ProjectCompany).where(ProjectCompany.project_id==project.id,ProjectCompany.company_id==company.id,ProjectCompany.project_role=="Client"))
    assert client.post(f"/projects/{project.id}/contacts",data={"contact_id":contact.id,"project_role":"Site Contact"}).status_code==200
    assert client.post(f"/projects/{project.id}/companies",data={"company_id":company.id,"project_role":"GC"}).status_code==200
    db.expire_all(); assert db.scalar(select(ProjectContact).where(ProjectContact.project_id==project.id,ProjectContact.contact_id==contact.id,ProjectContact.project_role=="Site Contact"))
    assert db.scalar(select(ProjectCompany).where(ProjectCompany.project_id==project.id,ProjectCompany.company_id==company.id,ProjectCompany.project_role=="GC"))
