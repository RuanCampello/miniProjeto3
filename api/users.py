import os
import uuid
from datetime import timedelta, datetime, timezone
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlmodel import select

from database import UserRegister, User, session_deps

user_router = APIRouter()

load_dotenv()

secret_key = os.getenv("AUTH_SECRET_KEY")
auth_algorithm = os.getenv("AUTH_ALGORITHM")

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth\token')
oauth2_bearer_dependency = Annotated[str, Depends(oauth2_bearer)]


def verify_password(plain_password, hashed_password):
    return bcrypt_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return bcrypt_context.hash(password)


def authenticate_user(username: str, password: str, db):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail=f'User {username} not found')

    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {'sub': username, 'id': str(user_id)}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, secret_key, algorithm=auth_algorithm)


@user_router.post("/register")
async def create_user(*, user: UserRegister, session: session_deps):
    user_db = User.model_validate(user)
    user_db.password = get_password_hash(user_db.password)

    statement = select(User).where(User.username == user_db.username)
    results = session.exec(statement).first()

    if results:
        raise HTTPException(status_code=409, detail="Username already taken")

    session.add(user_db)
    session.commit()
    session.refresh(user_db)

    return user_db.id


@user_router.post("/login")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: session_deps):
    try:
        user = authenticate_user(form_data.username, form_data.password, session)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    if not user:
        raise HTTPException(status_code=401, detail="Couldn't validate user")
    token = create_access_token(form_data.username, user.id, timedelta(minutes=20))

    return token


def get_current_user(token: str = Depends(oauth2_bearer)) -> uuid.UUID:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[auth_algorithm])
        user_id = payload.get("id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return uuid.UUID(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@user_router.get("/me")
async def get_me(token: oauth2_bearer_dependency, session: session_deps):
    try:
        user_id = get_current_user(token)
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")

        statement = select(User).where(User.id == user_id)
        user = session.exec(statement).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user = {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "profile_image": user.profile_image,
        }

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Couldn't validate user")
