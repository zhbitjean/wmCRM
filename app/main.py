import csv, io, json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from .auth import current_user, make_token, office_user, verify_password
from .database import get_db
from .models import ClientCompany, Contact, Project, ProjectContact, Property, StagedRecord, Unit, User, VerificationStatus
from .schemas import CompanyCreate, CompanyOut
from .search import digits, global_search

app=FastAPI(title="wmCRM",version="0.1.0")
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
    results=global_search(db,q) if q.strip() else []
    return templates.TemplateResponse(request,"home.html",{"q":q,"results":results,"user":user})
@app.get("/projects/{project_id}",response_class=HTMLResponse)
def project_detail(project_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    p=db.scalar(select(Project).where(Project.id==project_id).options(joinedload(Project.property),joinedload(Project.unit),joinedload(Project.client_company),joinedload(Project.contact_links).joinedload(ProjectContact.contact).joinedload(Contact.company)))
    if not p: raise HTTPException(404)
    return templates.TemplateResponse(request,"project.html",{"p":p,"user":user})
@app.get("/companies/{company_id}",response_class=HTMLResponse)
def company_detail(company_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    c=db.execute(select(ClientCompany).where(ClientCompany.id==company_id).options(joinedload(ClientCompany.contacts),joinedload(ClientCompany.projects).joinedload(Project.property))).unique().scalar_one_or_none()
    if not c: raise HTTPException(404)
    return templates.TemplateResponse(request,"company.html",{"c":c,"user":user})
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
    companies=db.scalars(select(ClientCompany).order_by(ClientCompany.company_name)).all(); contacts=db.scalars(select(Contact).order_by(Contact.display_name)).all(); properties=db.scalars(select(Property).order_by(Property.street_address)).all(); staged=db.scalars(select(StagedRecord).order_by(StagedRecord.imported_at.desc())).all()
    return templates.TemplateResponse(request,"admin.html",{"user":user,"companies":companies,"contacts":contacts,"properties":properties,"staged":staged})
@app.post("/admin/companies")
def add_company(company_name:str=Form(),phone:str|None=Form(None),email:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    db.add(ClientCompany(company_name=company_name,phone=phone,email=email,created_by=user.email,updated_by=user.email)); db.commit(); return RedirectResponse("/admin",303)
@app.post("/admin/contacts")
def add_contact(first_name:str=Form(),last_name:str=Form(),nickname:str|None=Form(None),role:str=Form("Other"),phone:str|None=Form(None),email:str|None=Form(None),company_id:int|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    db.add(Contact(first_name=first_name,last_name=last_name,display_name=f"{first_name} {last_name}".strip(),nickname=nickname or None,role=role,phone=phone,phone_normalized=digits(phone or ""),email=email,company_id=company_id,created_by=user.email,updated_by=user.email)); db.commit(); return RedirectResponse("/admin",303)
@app.post("/admin/contacts/{contact_id}")
def update_contact(contact_id:int,display_name:str=Form(),nickname:str|None=Form(None),role:str=Form("Other"),phone:str|None=Form(None),email:str|None=Form(None),notes:str|None=Form(None),db:Session=Depends(get_db),user:User=Depends(office_user)):
    c=db.get(Contact,contact_id)
    if not c: raise HTTPException(404)
    c.display_name=display_name; c.nickname=nickname or None; c.role=role; c.phone=phone; c.phone_normalized=digits(phone or ""); c.email=email; c.notes=notes; c.updated_by=user.email
    db.commit(); return RedirectResponse(f"/contacts/{contact_id}",303)
@app.post("/admin/import")
async def import_csv(file:UploadFile=File(),db:Session=Depends(get_db),user:User=Depends(office_user)):
    text=(await file.read()).decode("utf-8-sig"); reader=csv.DictReader(io.StringIO(text))
    for row in reader:
        kind=(row.pop("entity_type",None) or "contact").lower(); db.add(StagedRecord(entity_type=kind,payload_json=json.dumps(row),source_type="CSV",source_reference=file.filename,created_by=user.email))
    db.commit(); return RedirectResponse("/admin",303)
@app.post("/admin/staged/{record_id}/{action}")
def review(record_id:int,action:str,db:Session=Depends(get_db),user:User=Depends(office_user)):
    r=db.get(StagedRecord,record_id)
    if not r: raise HTTPException(404)
    if action=="reject": r.status=VerificationStatus.REJECTED
    elif action=="needs-correction": r.status=VerificationStatus.NEEDS_CORRECTION
    elif action=="approve":
        data=json.loads(r.payload_json); kind=r.entity_type.lower()
        if kind=="company": db.add(ClientCompany(company_name=data["company_name"],alternate_name=data.get("alternate_name"),phone=data.get("phone"),email=data.get("email"),notes=data.get("notes"),created_by=user.email))
        elif kind=="contact":
            first=data.get("first_name",""); last=data.get("last_name",""); phone=data.get("phone")
            db.add(Contact(first_name=first,last_name=last,display_name=data.get("display_name") or f"{first} {last}".strip(),nickname=data.get("nickname") or None,role=data.get("role","Other"),phone=phone,phone_normalized=digits(phone or ""),email=data.get("email"),verification_status=VerificationStatus.VERIFIED,last_verified_at=datetime.now(timezone.utc),created_by=user.email))
        else: raise HTTPException(400,"MVP approval supports contact and company records")
        r.status=VerificationStatus.VERIFIED
    else: raise HTTPException(400,"Unknown action")
    r.verified_by=user.email; r.verified_at=datetime.now(timezone.utc); r.updated_by=user.email; db.commit(); return RedirectResponse("/admin",303)

@app.get("/api/companies",response_model=list[CompanyOut])
def list_companies(db:Session=Depends(get_db),user:User=Depends(current_user)): return db.scalars(select(ClientCompany)).all()
@app.post("/api/companies",response_model=CompanyOut)
def create_company(data:CompanyCreate,db:Session=Depends(get_db),user:User=Depends(office_user)):
    row=ClientCompany(**data.model_dump(),created_by=user.email); db.add(row); db.commit(); db.refresh(row); return row
