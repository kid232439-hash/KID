from pydantic import BaseModel, EmailStr, Field

from .models import Role, SubscriberStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=12)
    role: Role = Role.support
    enable_mfa: bool = True


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}


class PlanCreate(BaseModel):
    name: str
    speed_down_mbps: int = Field(gt=0)
    speed_up_mbps: int = Field(gt=0)
    monthly_price: float = Field(ge=0)
    radius_group: str


class PlanOut(PlanCreate):
    id: int

    model_config = {"from_attributes": True}


class SubscriberCreate(BaseModel):
    account_no: str
    name: str
    phone: str
    email: EmailStr
    radius_username: str
    radius_password: str = Field(min_length=8)
    plan_id: int
    satellite_terminal_id: str | None = None


class SubscriberOut(BaseModel):
    id: int
    account_no: str
    name: str
    phone: str
    email: EmailStr
    radius_username: str
    status: SubscriberStatus
    plan_id: int
    balance: float
    satellite_terminal_id: str | None

    model_config = {"from_attributes": True}


class PaymentIn(BaseModel):
    account_no: str
    provider: str
    provider_reference: str
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    signature: str


class RadiusAuthorizeRequest(BaseModel):
    username: str
    password: str
    nas_ip_address: str | None = None


class RadiusAuthorizeResponse(BaseModel):
    allow: bool
    reply_message: str
    rate_limit: str | None = None
    radius_group: str | None = None


class RadiusAccountingRequest(BaseModel):
    username: str
    session_id: str | None = None
    input_octets: int = 0
    output_octets: int = 0
    status_type: str = "Interim-Update"


class SatelliteLinkRequest(BaseModel):
    account_no: str
    terminal_id: str
    provider: str = "satellite"
    api_key: str
