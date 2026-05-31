from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Role(str, Enum):
    super_admin = "super_admin"
    admin = "admin"
    support = "support"
    finance = "finance"
    installer = "installer"


class SubscriberStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    grace = "grace"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.support)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    speed_down_mbps: Mapped[int] = mapped_column(Integer)
    speed_up_mbps: Mapped[int] = mapped_column(Integer)
    monthly_price: Mapped[float] = mapped_column(Float)
    radius_group: Mapped[str] = mapped_column(String(120), unique=True)


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(255), index=True)
    radius_username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    radius_password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[SubscriberStatus] = mapped_column(
        SAEnum(SubscriberStatus), default=SubscriberStatus.grace
    )
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    satellite_terminal_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    plan: Mapped[Plan] = relationship()


class NasDevice(Base):
    __tablename__ = "nas_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    ip_address: Mapped[str] = mapped_column(String(64), unique=True)
    shared_secret: Mapped[str] = mapped_column(String(255))
    site: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id"))
    provider: Mapped[str] = mapped_column(String(64))
    provider_reference: Mapped[str] = mapped_column(String(120), unique=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    subscriber: Mapped[Subscriber] = relationship()


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    severity: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
