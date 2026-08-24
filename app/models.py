import enum
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now(): return datetime.now(timezone.utc)
class VerificationStatus(str, enum.Enum):
    PENDING="PENDING"; VERIFIED="VERIFIED"; REJECTED="REJECTED"; NEEDS_CORRECTION="NEEDS_CORRECTION"
class UserRole(str, enum.Enum): FIELD_USER="FIELD_USER"; OFFICE_USER="OFFICE_USER"; ADMIN="ADMIN"
class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    created_by: Mapped[str|None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str|None] = mapped_column(String(255), nullable=True)

class User(Base, AuditMixin):
    __tablename__="users"; id: Mapped[int]=mapped_column(primary_key=True)
    email: Mapped[str]=mapped_column(String(255), unique=True, index=True); password_hash: Mapped[str]=mapped_column(String(255)); role: Mapped[UserRole]=mapped_column(Enum(UserRole)); active: Mapped[bool]=mapped_column(Boolean, default=True)
class ClientCompany(Base, AuditMixin):
    __tablename__="client_companies"; id: Mapped[int]=mapped_column(primary_key=True)
    company_name: Mapped[str]=mapped_column(String(255), index=True); alternate_name: Mapped[str|None]=mapped_column(String(255)); phone: Mapped[str|None]=mapped_column(String(50)); fax: Mapped[str|None]=mapped_column(String(50)); email: Mapped[str|None]=mapped_column(String(255)); address: Mapped[str|None]=mapped_column(String(500)); notes: Mapped[str|None]=mapped_column(Text); active: Mapped[bool]=mapped_column(Boolean, default=True)
    contacts: Mapped[list["Contact"]]=relationship(back_populates="company"); projects: Mapped[list["Project"]]=relationship(back_populates="client_company")
class Contact(Base, AuditMixin):
    __tablename__="contacts"; id: Mapped[int]=mapped_column(primary_key=True)
    first_name: Mapped[str]=mapped_column(String(100)); last_name: Mapped[str]=mapped_column(String(100)); display_name: Mapped[str]=mapped_column(String(255), index=True); nickname: Mapped[str|None]=mapped_column(String(100), index=True); title: Mapped[str|None]=mapped_column(String(100)); role: Mapped[str|None]=mapped_column(String(100)); phone: Mapped[str|None]=mapped_column(String(50), index=True); phone_normalized: Mapped[str|None]=mapped_column(String(30), index=True); alternate_phone: Mapped[str|None]=mapped_column(String(50)); fax: Mapped[str|None]=mapped_column(String(50)); email: Mapped[str|None]=mapped_column(String(255), index=True); address: Mapped[str|None]=mapped_column(String(500)); company_id: Mapped[int|None]=mapped_column(ForeignKey("client_companies.id")); notes: Mapped[str|None]=mapped_column(Text); active: Mapped[bool]=mapped_column(Boolean, default=True); verification_status: Mapped[VerificationStatus]=mapped_column(Enum(VerificationStatus), default=VerificationStatus.PENDING); last_verified_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    company: Mapped[ClientCompany|None]=relationship(back_populates="contacts"); project_links: Mapped[list["ProjectContact"]]=relationship(back_populates="contact", cascade="all, delete-orphan")
class Property(Base, AuditMixin):
    __tablename__="properties"; id: Mapped[int]=mapped_column(primary_key=True)
    street_address: Mapped[str]=mapped_column(String(255), index=True); address_line_2: Mapped[str|None]=mapped_column(String(255)); city: Mapped[str]=mapped_column(String(100)); borough: Mapped[str|None]=mapped_column(String(50)); state: Mapped[str]=mapped_column(String(2)); zip_code: Mapped[str]=mapped_column(String(10)); building_name: Mapped[str|None]=mapped_column(String(255)); notes: Mapped[str|None]=mapped_column(Text)
    units: Mapped[list["Unit"]]=relationship(back_populates="property", cascade="all, delete-orphan"); projects: Mapped[list["Project"]]=relationship(back_populates="property")
    @property
    def full_address(self): return f"{self.street_address}, {self.city}, {self.state} {self.zip_code}"
class Unit(Base):
    __tablename__="units"; __table_args__=(UniqueConstraint("property_id","unit_number"),); id: Mapped[int]=mapped_column(primary_key=True); property_id: Mapped[int]=mapped_column(ForeignKey("properties.id")); unit_number: Mapped[str]=mapped_column(String(50), index=True); notes: Mapped[str|None]=mapped_column(Text)
    property: Mapped[Property]=relationship(back_populates="units"); projects: Mapped[list["Project"]]=relationship(back_populates="unit")
class Project(Base, AuditMixin):
    __tablename__="projects"; id: Mapped[int]=mapped_column(primary_key=True); project_name: Mapped[str]=mapped_column(String(255), index=True); client_company_id: Mapped[int|None]=mapped_column(ForeignKey("client_companies.id")); property_id: Mapped[int]=mapped_column(ForeignKey("properties.id")); unit_id: Mapped[int|None]=mapped_column(ForeignKey("units.id")); project_type: Mapped[str|None]=mapped_column(String(100)); status: Mapped[str]=mapped_column(String(50), default="Active"); description: Mapped[str|None]=mapped_column(Text); internal_notes: Mapped[str|None]=mapped_column(Text)
    client_company: Mapped[ClientCompany|None]=relationship(back_populates="projects"); property: Mapped[Property]=relationship(back_populates="projects"); unit: Mapped[Unit|None]=relationship(back_populates="projects"); contact_links: Mapped[list["ProjectContact"]]=relationship(back_populates="project", cascade="all, delete-orphan")
class ProjectContact(Base, AuditMixin):
    __tablename__="project_contacts"; __table_args__=(UniqueConstraint("project_id","contact_id","project_role"),); id: Mapped[int]=mapped_column(primary_key=True); project_id: Mapped[int]=mapped_column(ForeignKey("projects.id")); contact_id: Mapped[int]=mapped_column(ForeignKey("contacts.id")); project_role: Mapped[str]=mapped_column(String(100)); notes: Mapped[str|None]=mapped_column(Text)
    project: Mapped[Project]=relationship(back_populates="contact_links"); contact: Mapped[Contact]=relationship(back_populates="project_links")
class StagedRecord(Base, AuditMixin):
    __tablename__="staged_records"; id: Mapped[int]=mapped_column(primary_key=True); entity_type: Mapped[str]=mapped_column(String(50)); payload_json: Mapped[str]=mapped_column(Text); status: Mapped[VerificationStatus]=mapped_column(Enum(VerificationStatus), default=VerificationStatus.PENDING); source_type: Mapped[str]=mapped_column(String(50)); source_reference: Mapped[str|None]=mapped_column(String(500)); imported_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now); verified_by: Mapped[str|None]=mapped_column(String(255)); verified_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); review_notes: Mapped[str|None]=mapped_column(Text)
