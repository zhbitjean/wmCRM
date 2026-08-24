import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload
from .auth import current_user, make_token, office_user, verify_password
from .database import get_db
from .models import ClientCompany, Contact, Project, ProjectCompany, ProjectContact, Property, StagedRecord, Unit, User, VerificationStatus
from .importers import parse_csv, parse_current_client_xlsx
from .duplicates import annotate_duplicate
from .geography import BOROUGHS, infer_nyc_borough
from .schemas import CompanyCreate, CompanyOut
from .search import digits, directory_search, global_search

app=FastAPI(title="WM CRM",version="0.1.0")
BASE=Path(__file__).parent
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
templates=Jinja2Templates(directory=BASE/"templates")

@app.exception_handler(401)
def unauthorized(request, exc): return RedirectResponse("/login",303)
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/login",response_class=HTMLResponse)
def login_page(request:Request): return templates.TemplateResponse(request,"login.html",{})
@app.post("/login")
def login(email:str=Form(),password:str=Form(),db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==email.lower()))
    if not user or not verify_password(password,user.password_hash): return RedirectResponse("/login?error=1",303)
    response=RedirectResponse("/",303); response.set_cookie("access_token",make_token(user),httponly=True,samesite="lax",max_age=28800); return response
@app.post("/logout")
def logout():
    response=RedirectResponse("/login",303); response.delete_cookie("access_token"); return response
@app.get("/",response_class=HTMLResponse)
def home(request:Request,q:str="",db:Session=Depends(get_db),user:User=Depends(current_user)):
    results=global_search(db,q) if q.strip() else []; contacts,companies=directory_search(db,q) if q.strip() else ([],[])
    return templates.TemplateResponse(request,"home.html",{"q":q,"results":results,"contacts":contacts,"companies":companies,"total_results":len(results)+len(contacts)+len(companies),"user":user})
@app.get("/projects",response_class=HTMLResponse)
def project_list(request:Request,q:str="",status:str="",borough:str="",db:Session=Depends(get_db),user:User=Depends(current_user)):
    stmt=select(Project).join(Property).options(joinedload(Project.property),joinedload(Project.unit),joinedload(Project.client_company),joinedload(Project.contact_links))
    if q.strip():
        pattern=f"%{q.strip()}%"; stmt=stmt.where(or_(Project.project_name.ilike(pattern),Property.street_address.ilike(pattern),Property.city.ilike(pattern)))
    if status: stmt=stmt.where(Project.status==status)
    if borough: stmt=stmt.where(Property.borough==borough)
    projects=db.execute(stmt.order_by(Project.updated_at.desc())).unique().scalars().all()
    statuses=db.scalars(select(Project.status).distinct().order_by(Project.status)).all()
    return templates.TemplateResponse(request,"projects.html",{"projects":projects,"q":q,"selected_status":status,"selected_borough":borough,"statuses":statuses,"boroughs":BOROUGHS,"user":user})
@app.get("/projects/new",response_class=HTMLResponse)
def new_project_page(request:Request,db:Session=Depends(get_db),user:User=Depends(office_user)):
    companies=db.scalars(select(ClientCompany).order_by(ClientCompany.company_name)).all()
    return templates.TemplateResponse(request,"project_form.html",{"companies":companies,"boroughs":BOROUGHS,"user":user})
@app.post("/projects/new")
def create_project_direct(project_name:str=Form(),street_address:str=Form(),city:str=Form(),state:str=Form("NY"),zip_code:str=Form(""),borough:str|None=Form(None),unit_number:str|None=Form(None),project_type:str|None=Form(None),status:str=Form("Active"),client_company_id:int|None=Form(None),description:str|None=Form(None),internal_notes:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    chosen_borough=borough or infer_nyc_borough(f"{street_address}, {city}, {state}")
    property_row=Property(street_address=street_address.strip(),city=city.strip(),borough=chosen_borough,state=state.strip().upper(),zip_code=zip_code.strip(),created_by=user.email,updated_by=user.email)
    unit=Unit(property=property_row,unit_number=unit_number.strip()) if unit_number and unit_number.strip() else None
    project=Project(project_name=project_name.strip(),client_company_id=client_company_id,property=property_row,unit=unit,project_type=project_type or None,status=status,description=description or None,internal_notes=internal_notes or None,created_by=user.email,updated_by=user.email)
    if client_company_id: project.company_links.append(ProjectCompany(company_id=client_company_id,project_role="Client",created_by=user.email,updated_by=user.email))
    db.add(project); db.commit(); db.refresh(project); return RedirectResponse(f"/projects/{project.id}",303)
@app.get("/projects/{project_id}",response_class=HTMLResponse)
def project_detail(project_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    p=db.execute(select(Project).where(Project.id==project_id).options(joinedload(Project.property),joinedload(Project.unit),joinedload(Project.client_company),joinedload(Project.contact_links).joinedload(ProjectContact.contact).joinedload(Contact.company),joinedload(Project.company_links).joinedload(ProjectCompany.company))).unique().scalar_one_or_none()
    if not p: raise HTTPException(404)
    contacts=db.scalars(select(Contact).where(Contact.active==True).order_by(Contact.display_name)).all() if user.role.value in ("ADMIN","OFFICE_USER") else []
    companies=db.scalars(select(ClientCompany).where(ClientCompany.active==True).order_by(ClientCompany.company_name)).all() if user.role.value in ("ADMIN","OFFICE_USER") else []
    return templates.TemplateResponse(request,"project.html",{"p":p,"contacts":contacts,"companies":companies,"user":user})
@app.post("/projects/{project_id}/contacts")
def add_project_contact(project_id:int,contact_id:int=Form(),project_role:str=Form(),notes:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    if not db.get(Project,project_id) or not db.get(Contact,contact_id): raise HTTPException(404)
    exists=db.scalar(select(ProjectContact).where(ProjectContact.project_id==project_id,ProjectContact.contact_id==contact_id,ProjectContact.project_role==project_role))
    if not exists: db.add(ProjectContact(project_id=project_id,contact_id=contact_id,project_role=project_role.strip(),notes=notes or None,created_by=user.email,updated_by=user.email)); db.commit()
    return RedirectResponse(f"/projects/{project_id}",303)
@app.post("/projects/{project_id}/companies")
def add_project_company(project_id:int,company_id:int=Form(),project_role:str=Form(),notes:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    if not db.get(Project,project_id) or not db.get(ClientCompany,company_id): raise HTTPException(404)
    exists=db.scalar(select(ProjectCompany).where(ProjectCompany.project_id==project_id,ProjectCompany.company_id==company_id,ProjectCompany.project_role==project_role))
    if not exists: db.add(ProjectCompany(project_id=project_id,company_id=company_id,project_role=project_role.strip(),notes=notes or None,created_by=user.email,updated_by=user.email)); db.commit()
    return RedirectResponse(f"/projects/{project_id}",303)
@app.get("/contacts",response_class=HTMLResponse)
def contact_list(request:Request,q:str="",db:Session=Depends(get_db),user:User=Depends(current_user)):
    stmt=select(Contact).options(joinedload(Contact.company)).order_by(Contact.display_name)
    if q.strip(): stmt=stmt.where(or_(Contact.display_name.ilike(f"%{q}%"),Contact.nickname.ilike(f"%{q}%"),Contact.phone.ilike(f"%{q}%"),Contact.email.ilike(f"%{q}%")))
    return templates.TemplateResponse(request,"contacts.html",{"contacts":db.execute(stmt).unique().scalars().all(),"q":q,"user":user})
@app.get("/companies",response_class=HTMLResponse)
def company_list(request:Request,q:str="",db:Session=Depends(get_db),user:User=Depends(current_user)):
    stmt=select(ClientCompany).order_by(ClientCompany.company_name)
    if q.strip(): stmt=stmt.where(or_(ClientCompany.company_name.ilike(f"%{q}%"),ClientCompany.phone.ilike(f"%{q}%"),ClientCompany.email.ilike(f"%{q}%")))
    return templates.TemplateResponse(request,"companies.html",{"companies":db.scalars(stmt).all(),"q":q,"user":user})
@app.get("/companies/new",response_class=HTMLResponse)
def new_company_page(request:Request,user:User=Depends(office_user)):
    return templates.TemplateResponse(request,"company_form.html",{"boroughs":BOROUGHS,"user":user})
@app.post("/companies/new")
def create_company_direct(company_name:str=Form(),alternate_name:str|None=Form(None),phone:str|None=Form(None),fax:str|None=Form(None),email:str|None=Form(None),address:str|None=Form(None),borough:str|None=Form(None),notes:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    company=ClientCompany(company_name=company_name.strip(),alternate_name=alternate_name or None,phone=phone or None,fax=fax or None,email=email or None,address=address or None,borough=borough or infer_nyc_borough(address),notes=notes or None,created_by=user.email,updated_by=user.email)
    db.add(company); db.commit(); db.refresh(company); return RedirectResponse(f"/companies/{company.id}",303)
@app.get("/companies/{company_id}",response_class=HTMLResponse)
def company_detail(company_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    c=db.execute(select(ClientCompany).where(ClientCompany.id==company_id).options(joinedload(ClientCompany.contacts),joinedload(ClientCompany.projects).joinedload(Project.property),joinedload(ClientCompany.project_links).joinedload(ProjectCompany.project).joinedload(Project.property))).unique().scalar_one_or_none()
    if not c: raise HTTPException(404)
    return templates.TemplateResponse(request,"company.html",{"c":c,"user":user})
@app.get("/contacts/new",response_class=HTMLResponse)
def new_contact_page(request:Request,db:Session=Depends(get_db),user:User=Depends(office_user)):
    companies=db.scalars(select(ClientCompany).order_by(ClientCompany.company_name)).all()
    return templates.TemplateResponse(request,"contact_form.html",{"companies":companies,"boroughs":BOROUGHS,"user":user})
@app.post("/contacts/new")
def create_contact_direct(first_name:str=Form(),last_name:str=Form(),nickname:str|None=Form(None),role:str=Form("Other"),phone:str|None=Form(None),alternate_phone:str|None=Form(None),fax:str|None=Form(None),email:str|None=Form(None),address:str|None=Form(None),borough:str|None=Form(None),company_id:int|None=Form(None),notes:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    contact=Contact(first_name=first_name.strip(),last_name=last_name.strip(),display_name=f"{first_name.strip()} {last_name.strip()}".strip(),nickname=nickname or None,role=role or "Other",phone=phone or None,phone_normalized=digits(phone or ""),alternate_phone=alternate_phone or None,fax=fax or None,email=email or None,address=address or None,borough=borough or infer_nyc_borough(address),company_id=company_id,notes=notes or None,verification_status=VerificationStatus.VERIFIED,last_verified_at=datetime.now(timezone.utc),created_by=user.email,updated_by=user.email)
    db.add(contact); db.commit(); db.refresh(contact); return RedirectResponse(f"/contacts/{contact.id}",303)
@app.get("/contacts/{contact_id}",response_class=HTMLResponse)
def contact_detail(contact_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    c=db.execute(select(Contact).where(Contact.id==contact_id).options(joinedload(Contact.company),joinedload(Contact.project_links).joinedload(ProjectContact.project).joinedload(Project.property))).unique().scalar_one_or_none()
    if not c: raise HTTPException(404)
    return templates.TemplateResponse(request,"contact.html",{"c":c,"user":user})
@app.get("/properties/{property_id}",response_class=HTMLResponse)
def property_detail(property_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    p=db.execute(select(Property).where(Property.id==property_id).options(joinedload(Property.units),joinedload(Property.projects).joinedload(Project.client_company))).unique().scalar_one_or_none()
    if not p: raise HTTPException(404)
    return templates.TemplateResponse(request,"property.html",{"p":p,"user":user})

@app.get("/admin",response_class=HTMLResponse)
def admin(request:Request,db:Session=Depends(get_db),user:User=Depends(office_user)):
    staged=db.scalars(select(StagedRecord).order_by(StagedRecord.imported_at.desc())).all()
    review_items=[{"record":r,"payload":json.loads(r.payload_json),"reasons":json.loads(r.duplicate_reasons) if r.duplicate_reasons else []} for r in staged]
    return templates.TemplateResponse(request,"admin.html",{"user":user,"review_items":review_items})
@app.post("/admin/companies")
def add_company(company_name:str=Form(),phone:str|None=Form(None),email:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    db.add(ClientCompany(company_name=company_name,phone=phone,email=email,created_by=user.email,updated_by=user.email)); db.commit(); return RedirectResponse("/admin",303)
@app.post("/admin/contacts")
def add_contact(first_name:str=Form(),last_name:str=Form(),nickname:str|None=Form(None),role:str=Form("Other"),phone:str|None=Form(None),email:str|None=Form(None),company_id:int|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    db.add(Contact(first_name=first_name,last_name=last_name,display_name=f"{first_name} {last_name}".strip(),nickname=nickname or None,role=role,phone=phone,phone_normalized=digits(phone or ""),email=email,company_id=company_id,created_by=user.email,updated_by=user.email)); db.commit(); return RedirectResponse("/admin",303)
@app.post("/admin/contacts/{contact_id}")
def update_contact(contact_id:int,display_name:str=Form(),nickname:str|None=Form(None),role:str=Form("Other"),phone:str|None=Form(None),fax:str|None=Form(None),email:str|None=Form(None),address:str|None=Form(None),borough:str|None=Form(None),notes:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    c=db.get(Contact,contact_id)
    if not c: raise HTTPException(404)
    c.display_name=display_name; c.nickname=nickname or None; c.role=role; c.phone=phone; c.phone_normalized=digits(phone or ""); c.fax=fax or None; c.email=email; c.address=address or None; c.borough=borough or infer_nyc_borough(address); c.notes=notes; c.updated_by=user.email
    db.commit(); return RedirectResponse(f"/contacts/{contact_id}",303)
@app.post("/admin/import")
async def import_file(file:UploadFile=File(),db:Session=Depends(get_db),user:User=Depends(office_user)):
    content=await file.read(); suffix=Path(file.filename or "").suffix.lower()
    try:
        if suffix==".xlsx":
            rows,skipped=parse_current_client_xlsx(content); source_type="EXCEL"
            for row in rows:
                record=StagedRecord(entity_type="client_bundle",payload_json=json.dumps(row),source_type=source_type,source_reference=f"{file.filename} / current client list",created_by=user.email); db.add(annotate_duplicate(db,record,row))
        elif suffix==".csv":
            rows=parse_csv(content); skipped=[]; source_type="CSV"
            for row in rows:
                kind=(row.pop("entity_type",None) or "contact").lower(); record=StagedRecord(entity_type=kind,payload_json=json.dumps(row),source_type=source_type,source_reference=file.filename,created_by=user.email)
                db.add(annotate_duplicate(db,record,row) if kind=="contact" else record)
        else: raise ValueError("Upload an .xlsx or .csv file")
    except (ValueError,UnicodeDecodeError) as exc:
        return RedirectResponse(f"/admin?import_error={quote(str(exc))}",303)
    db.commit(); return RedirectResponse(f"/admin?imported={len(rows)}&skipped={len(skipped)}",303)
@app.post("/admin/staged/{record_id}/{action}")
def review(record_id:int,action:str,db:Session=Depends(get_db),user:User=Depends(office_user)):
    r=db.get(StagedRecord,record_id)
    if not r: raise HTTPException(404)
    if action in ("reject","skip"):
        r.status=VerificationStatus.REJECTED; r.review_notes="Skipped as possible duplicate" if action=="skip" else "Rejected by reviewer"
    elif action=="needs-correction": r.status=VerificationStatus.NEEDS_CORRECTION
    elif action in ("update-existing","merge"):
        if r.entity_type.lower()!="client_bundle" or not r.duplicate_contact_id: raise HTTPException(400,"No existing contact candidate is available")
        data=json.loads(r.payload_json); contact=db.get(Contact,r.duplicate_contact_id)
        fields={"display_name":data.get("display_name"),"nickname":data.get("nickname"),"role":data.get("role"),"phone":data.get("phone"),"alternate_phone":data.get("alternate_phone"),"fax":data.get("fax"),"email":data.get("email"),"address":data.get("address"),"borough":data.get("borough") or infer_nyc_borough(data.get("address")),"notes":data.get("notes")}
        for key,value in fields.items():
            if value is not None and (action=="update-existing" or not getattr(contact,key,None)): setattr(contact,key,value)
        contact.phone_normalized=digits(contact.phone or "")
        if not contact.company_id and r.duplicate_company_id: contact.company_id=r.duplicate_company_id
        contact.verification_status=VerificationStatus.VERIFIED; contact.last_verified_at=datetime.now(timezone.utc); contact.updated_by=user.email
        r.status=VerificationStatus.VERIFIED; r.review_notes="Updated existing contact" if action=="update-existing" else "Merged missing fields into existing contact"
    elif action=="approve":
        data=json.loads(r.payload_json); kind=r.entity_type.lower()
        if kind=="company": db.add(ClientCompany(company_name=data["company_name"],alternate_name=data.get("alternate_name"),phone=data.get("phone"),fax=data.get("fax"),email=data.get("email"),address=data.get("address"),borough=data.get("borough") or infer_nyc_borough(data.get("address")),notes=data.get("notes"),created_by=user.email))
        elif kind=="contact":
            first=data.get("first_name",""); last=data.get("last_name",""); phone=data.get("phone")
            db.add(Contact(first_name=first,last_name=last,display_name=data.get("display_name") or f"{first} {last}".strip(),nickname=data.get("nickname") or None,role=data.get("role","Other"),phone=phone,phone_normalized=digits(phone or ""),email=data.get("email"),address=data.get("address"),borough=data.get("borough") or infer_nyc_borough(data.get("address")),verification_status=VerificationStatus.VERIFIED,last_verified_at=datetime.now(timezone.utc),created_by=user.email))
        elif kind=="client_bundle":
            company=None; company_name=data.get("company_name")
            if company_name:
                company=db.scalar(select(ClientCompany).where(ClientCompany.company_name.ilike(company_name)))
                if not company:
                    company=ClientCompany(company_name=company_name,phone=data.get("company_phone"),fax=data.get("company_fax"),email=data.get("email"),address=data.get("company_address"),borough=data.get("borough") or infer_nyc_borough(data.get("company_address")),created_by=user.email,updated_by=user.email); db.add(company); db.flush()
            db.add(Contact(first_name=data.get("first_name") or "",last_name=data.get("last_name") or "",display_name=data["display_name"],nickname=data.get("nickname"),role=data.get("role") or "Client",phone=data.get("phone"),phone_normalized=digits(data.get("phone") or ""),alternate_phone=data.get("alternate_phone"),fax=data.get("fax"),email=data.get("email"),address=data.get("address"),borough=data.get("borough") or infer_nyc_borough(data.get("address")),company=company,notes=data.get("notes"),verification_status=VerificationStatus.VERIFIED,last_verified_at=datetime.now(timezone.utc),created_by=user.email,updated_by=user.email))
        else: raise HTTPException(400,"Unsupported staged record type")
        r.status=VerificationStatus.VERIFIED
    else: raise HTTPException(400,"Unknown action")
    r.verified_by=user.email; r.verified_at=datetime.now(timezone.utc); r.updated_by=user.email; db.commit(); return RedirectResponse("/admin",303)

@app.get("/api/companies",response_model=list[CompanyOut])
def list_companies(db:Session=Depends(get_db),user:User=Depends(current_user)): return db.scalars(select(ClientCompany)).all()
@app.post("/api/companies",response_model=CompanyOut)
def create_company(data:CompanyCreate,db:Session=Depends(get_db),user:User=Depends(office_user)):
    row=ClientCompany(**data.model_dump(),created_by=user.email); db.add(row); db.commit(); db.refresh(row); return row
