from pydantic import BaseModel, ConfigDict
class CompanyCreate(BaseModel):
    company_name: str; alternate_name: str|None=None; phone: str|None=None; email: str|None=None; notes: str|None=None
class CompanyOut(CompanyCreate):
    id: int; active: bool; model_config=ConfigDict(from_attributes=True)

