from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Role, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
settings = get_settings()

ADMIN_ROLES = {Role.super_admin, Role.admin}
SECURITY_ROLES = {Role.super_admin, Role.admin, Role.support}
FINANCE_ROLES = {Role.super_admin, Role.admin, Role.finance}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, role: Role) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": subject, "role": role.value, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_totp(secret: str | None, code: str | None) -> bool:
    if not secret:
        return True
    return bool(code and pyotp.TOTP(secret).verify(code, valid_window=1))


def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str | None = payload.get("sub")
    except JWTError as exc:
        raise credentials_exception from exc
    if email is None:
        raise credentials_exception
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user is None:
        raise credentials_exception
    return user


def require_roles(*roles: Role):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency


def admin_only(user: User = Depends(current_user)) -> User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user
