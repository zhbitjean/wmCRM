import json
from difflib import SequenceMatcher
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from .models import ClientCompany, Contact
from .search import digits

def normalized_text(value):
    return " ".join((value or "").lower().strip().split())

def similarity(left, right):
    left=normalized_text(left); right=normalized_text(right)
    return SequenceMatcher(None,left,right).ratio() if left and right else 0.0

def find_duplicate(db: Session, payload: dict):
    reasons=[]; candidate_contact=None; candidate_company=None
    phone=digits(payload.get("phone") or ""); email=normalized_text(payload.get("email")); name=payload.get("display_name") or ""; company_name=payload.get("company_name") or ""
    if phone:
        candidate_contact=db.scalar(select(Contact).where(Contact.phone_normalized==phone))
        if candidate_contact: reasons.append("Exact normalized phone match")
    if email:
        email_match=db.scalar(select(Contact).where(func.lower(func.trim(Contact.email))==email))
        if email_match:
            if candidate_contact is None: candidate_contact=email_match
            if email_match.id==candidate_contact.id: reasons.append("Exact email match")
            else: reasons.append(f"Email matches another contact: {email_match.display_name}")
    companies=db.scalars(select(ClientCompany)).all() if company_name else []
    for company in companies:
        score=similarity(company.company_name,company_name)
        if score>=0.88:
            candidate_company=company
            reasons.append(f"Similar company name ({round(score*100)}%)")
            break
    if candidate_contact is None and name:
        contacts=db.scalars(select(Contact).where(Contact.company_id==candidate_company.id if candidate_company else Contact.company_id.is_(None))).all()
        for contact in contacts:
            score=similarity(contact.display_name,name)
            if score>=0.82:
                candidate_contact=contact; reasons.append(f"Similar name with same company ({round(score*100)}%)"); break
    return candidate_contact,candidate_company,reasons

def annotate_duplicate(db: Session, record, payload: dict):
    contact,company,reasons=find_duplicate(db,payload)
    record.duplicate_contact_id=contact.id if contact else None
    record.duplicate_company_id=company.id if company else None
    record.duplicate_reasons=json.dumps(reasons) if reasons else None
    return record

