import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import Token, UserLogin, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_MAX_FAILURES = 10
_LOGIN_WINDOW_SECONDS = 300.0
# Keyed by (client IP, email) so clients sharing an IP (proxies, NAT)
# cannot lock each other out.
_login_failures: dict[tuple[str, str], deque] = defaultdict(deque)
_login_lock = Lock()


@router.post("/register", response_model=Token, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)) -> Token:
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled",
        )
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    is_first_user = db.query(User).first() is None
    is_admin = is_first_user or (
        settings.admin_email is not None and data.email.lower() == settings.admin_email.lower()
    )
    user = User(
        email=data.email,
        display_name=data.display_name,
        hashed_password=hash_password(data.password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    access_token = create_access_token({"sub": user.id})
    return Token(access_token=access_token)


@router.post("/login", response_model=Token)
def login(
    data: UserLogin, request: Request, db: Session = Depends(get_db)
) -> Token:
    ip = request.client.host if request.client else "unknown"
    key = (ip, data.email.lower())
    now = time.monotonic()
    with _login_lock:
        failures = _login_failures.get(key)
        if failures is not None:
            while failures and now - failures[0] > _LOGIN_WINDOW_SECONDS:
                failures.popleft()
            if not failures:
                del _login_failures[key]
            elif len(failures) >= _LOGIN_MAX_FAILURES:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts, try again later",
                )

    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        with _login_lock:
            _login_failures[key].append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    with _login_lock:
        _login_failures.pop(key, None)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token({"sub": user.id})
    return Token(access_token=access_token)
