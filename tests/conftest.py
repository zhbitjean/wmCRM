import os
os.environ["DATABASE_URL"]="sqlite://"
os.environ["SECRET_KEY"]="test-secret"
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.auth import hash_password
from app.models import User, UserRole

engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
TestingSession=sessionmaker(bind=engine,expire_on_commit=False)
@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(engine)
    db=TestingSession(); db.add_all([User(email="admin@test.com",password_hash=hash_password("password"),role=UserRole.ADMIN),User(email="field@test.com",password_hash=hash_password("password"),role=UserRole.FIELD_USER)]); db.commit(); db.close()
    yield
    Base.metadata.drop_all(engine)
@pytest.fixture
def db():
    s=TestingSession(); yield s; s.close()
@pytest.fixture
def client():
    def override():
        s=TestingSession()
        try: yield s
        finally: s.close()
    app.dependency_overrides[get_db]=override
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear()
def login(client,email="admin@test.com"):
    return client.post("/login",data={"email":email,"password":"password"})

