import hmac

import pyotp
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_db
from .models import NasDevice, Payment, Plan, Role, SecurityEvent, Subscriber, SubscriberStatus, User
from .schemas import (
    LoginRequest,
    PaymentIn,
    PlanCreate,
    PlanOut,
    RadiusAccountingRequest,
    RadiusAuthorizeRequest,
    RadiusAuthorizeResponse,
    SatelliteLinkRequest,
    SubscriberCreate,
    SubscriberOut,
    Token,
    UserCreate,
    UserOut,
)
from .security import (
    FINANCE_ROLES,
    SECURITY_ROLES,
    admin_only,
    create_access_token,
    hash_password,
    require_roles,
    verify_password,
    verify_totp,
)

settings = get_settings()
app = FastAPI(
    title="JAGUAR TECHNOLOGIES ISP Platform",
    description="Wi-Fi billing, FreeRADIUS integration, global payments, security, and satellite linking.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

static_dir = settings.static_dir
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


def seed_database() -> None:
    db = next(get_db())
    try:
        if not db.query(User).filter(User.email == settings.admin_email).first():
            user = User(
                email=settings.admin_email,
                full_name="JAGUAR Root Administrator",
                password_hash=hash_password(settings.admin_password),
                role=Role.super_admin,
                mfa_secret=None,
            )
            db.add(user)
        if not db.query(Plan).first():
            db.add_all(
                [
                    Plan(
                        name="Orange Home 20",
                        speed_down_mbps=20,
                        speed_up_mbps=5,
                        monthly_price=29.0,
                        radius_group="orange-home-20",
                    ),
                    Plan(
                        name="Orange Business 100",
                        speed_down_mbps=100,
                        speed_up_mbps=40,
                        monthly_price=149.0,
                        radius_group="orange-business-100",
                    ),
                ]
            )
        db.commit()
    finally:
        db.close()


seed_database()


@app.get("/", include_in_schema=False)
def web_index():
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": settings.app_name, "status": "frontend not installed"}


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(static_dir / "manifest.webmanifest")


@app.get("/service-worker.js", include_in_schema=False)
def service_worker():
    return FileResponse(static_dir / "service-worker.js")


@app.get("/api/health")
def health():
    return {"status": "ok", "name": settings.app_name, "environment": settings.environment}


@app.post("/api/auth/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login")
    if not verify_totp(user.mfa_secret, payload.totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA code required")
    return {"access_token": create_access_token(user.email, user.role), "role": user.role}


@app.post("/api/admin/users", response_model=UserOut, dependencies=[Depends(admin_only)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        mfa_secret=pyotp.random_base32() if payload.enable_mfa else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/admin/users", response_model=list[UserOut], dependencies=[Depends(admin_only)])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@app.post("/api/plans", response_model=PlanOut, dependencies=[Depends(admin_only)])
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)):
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@app.get("/api/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return db.query(Plan).order_by(Plan.monthly_price).all()


@app.post("/api/subscribers", response_model=SubscriberOut, dependencies=[Depends(admin_only)])
def create_subscriber(payload: SubscriberCreate, db: Session = Depends(get_db)):
    if not db.get(Plan, payload.plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
    subscriber = Subscriber(
        account_no=payload.account_no,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        radius_username=payload.radius_username,
        radius_password_hash=hash_password(payload.radius_password),
        status=SubscriberStatus.grace,
        plan_id=payload.plan_id,
        satellite_terminal_id=payload.satellite_terminal_id,
    )
    db.add(subscriber)
    db.commit()
    db.refresh(subscriber)
    return subscriber


@app.get("/api/subscribers", response_model=list[SubscriberOut], dependencies=[Depends(require_roles(*SECURITY_ROLES, *FINANCE_ROLES))])
def list_subscribers(db: Session = Depends(get_db)):
    return db.query(Subscriber).order_by(Subscriber.id.desc()).limit(200).all()


@app.post("/api/payments/webhook")
def payment_webhook(payload: PaymentIn, db: Session = Depends(get_db)):
    expected = hmac.new(
        settings.payment_webhook_secret.encode(),
        f"{payload.provider_reference}:{payload.amount}:{payload.currency}".encode(),
        "sha256",
    ).hexdigest()
    if not hmac.compare_digest(expected, payload.signature):
        raise HTTPException(status_code=401, detail="Invalid payment signature")
    subscriber = db.query(Subscriber).filter(Subscriber.account_no == payload.account_no).first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    if db.query(Payment).filter(Payment.provider_reference == payload.provider_reference).first():
        return {"status": "duplicate_ignored"}
    payment = Payment(
        subscriber_id=subscriber.id,
        provider=payload.provider,
        provider_reference=payload.provider_reference,
        amount=payload.amount,
        currency=payload.currency.upper(),
        status="settled",
    )
    subscriber.balance += payload.amount
    subscriber.status = SubscriberStatus.active if subscriber.balance >= 0 else SubscriberStatus.grace
    db.add(payment)
    db.commit()
    return {"status": "accepted", "account_no": subscriber.account_no, "balance": subscriber.balance}


@app.post("/api/radius/authorize", response_model=RadiusAuthorizeResponse)
def radius_authorize(
    payload: RadiusAuthorizeRequest,
    db: Session = Depends(get_db),
    x_radius_secret: str = Header(default=""),
):
    if not hmac.compare_digest(x_radius_secret, settings.freeradius_shared_secret):
        raise HTTPException(status_code=401, detail="Invalid RADIUS shared secret")
    subscriber = (
        db.query(Subscriber).filter(Subscriber.radius_username == payload.username).first()
    )
    if not subscriber or not verify_password(payload.password, subscriber.radius_password_hash):
        db.add(SecurityEvent(severity="high", source="radius", message=f"Failed login: {payload.username}"))
        db.commit()
        return {"allow": False, "reply_message": "Invalid credentials"}
    if subscriber.status == SubscriberStatus.suspended:
        return {"allow": False, "reply_message": "Account suspended"}
    plan = subscriber.plan
    return {
        "allow": True,
        "reply_message": "Access granted by JAGUAR TECHNOLOGIES",
        "rate_limit": f"{plan.speed_down_mbps}M/{plan.speed_up_mbps}M",
        "radius_group": plan.radius_group,
    }


@app.post("/api/radius/accounting")
def radius_accounting(
    payload: RadiusAccountingRequest,
    db: Session = Depends(get_db),
    x_radius_secret: str = Header(default=""),
):
    if not hmac.compare_digest(x_radius_secret, settings.freeradius_shared_secret):
        raise HTTPException(status_code=401, detail="Invalid RADIUS shared secret")
    db.add(
        SecurityEvent(
            severity="info",
            source="radius-accounting",
            message=(
                f"{payload.status_type} for {payload.username} session={payload.session_id} "
                f"in={payload.input_octets} out={payload.output_octets}"
            ),
        )
    )
    db.commit()
    return {"status": "recorded"}


@app.post("/api/satellite/link", dependencies=[Depends(admin_only)])
def link_satellite(payload: SatelliteLinkRequest, db: Session = Depends(get_db)):
    if not hmac.compare_digest(payload.api_key, settings.satellite_api_key):
        raise HTTPException(status_code=401, detail="Invalid satellite integration key")
    subscriber = db.query(Subscriber).filter(Subscriber.account_no == payload.account_no).first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    subscriber.satellite_terminal_id = payload.terminal_id
    db.add(
        SecurityEvent(
            severity="info",
            source=payload.provider,
            message=f"Linked terminal {payload.terminal_id} to {payload.account_no}",
        )
    )
    db.commit()
    return {"status": "linked", "terminal_id": payload.terminal_id}


@app.get("/api/security/events", dependencies=[Depends(require_roles(*SECURITY_ROLES))])
def security_events(db: Session = Depends(get_db)):
    return db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(100).all()


@app.get("/api/dashboard", dependencies=[Depends(require_roles(*SECURITY_ROLES, *FINANCE_ROLES))])
def dashboard(db: Session = Depends(get_db)):
    return {
        "subscribers": db.query(func.count(Subscriber.id)).scalar(),
        "active_subscribers": db.query(func.count(Subscriber.id))
        .filter(Subscriber.status == SubscriberStatus.active)
        .scalar(),
        "monthly_revenue": db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.status == "settled").scalar(),
        "nas_devices": db.query(func.count(NasDevice.id)).scalar(),
        "security_events": db.query(func.count(SecurityEvent.id)).scalar(),
    }


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response
