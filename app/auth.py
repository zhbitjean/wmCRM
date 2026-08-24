from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User, UserRole

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(value: str): return pwd.hash(value)
def verify_password(value: str, hashed: str): return pwd.verify(value, hashed)
def make_token(user: User):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub":str(user.id),"role":user.role.value,"exp":exp}, settings.secret_key, algorithm="HS256")
def current_user(request: Request, db: Session=Depends(get_db)):
    token=request.cookies.get("access_token")
    if not token: raise HTTPException(status_code=401, detail="Sign in required")
    try: uid=int(jwt.decode(token,settings.secret_key,algorithms=["HS256"])["sub"])
    except (JWTError, KeyError, ValueError): raise HTTPException(status_code=401, detail="Invalid session")
    user=db.get(User,uid)
    if not user or not user.active: raise HTTPException(status_code=401, detail="Inactive account")
    return user
def office_user(user: User=Depends(current_user)):
    if user.role not in (UserRole.ADMIN,UserRole.OFFICE_USER): raise HTTPException(status_code=403,detail="Office access required")
    return user

