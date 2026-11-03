from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class PermissionResponse(BaseModel):
    id: str
    description: str


class RoleResponse(BaseModel):
    id: str
    name: str
    permissions: list[PermissionResponse]


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: RoleResponse


class StaffCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank.")
        return value


class StaffResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: str
    role: RoleResponse


class PermissionOption(BaseModel):
    id: str
    description: str
    granted: bool


class RolePermissionsResponse(BaseModel):
    role_id: str
    role_name: str
    permissions: list[PermissionOption]


class RolePermissionsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission_ids: list[str] = Field(max_length=30)

    @field_validator("permission_ids")
    @classmethod
    def unique_permission_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Permission identifiers must be unique.")
        return values


class BusinessSettingsResponse(BaseModel):
    business_name: str
    currency: str
    timezone: str
    payment_methods: list[str]

    model_config = ConfigDict(from_attributes=True)


class BusinessSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str = Field(min_length=1, max_length=64)
    payment_methods: list[str] = Field(min_length=1, max_length=20)

    @field_validator("business_name", "timezone")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Enter a valid IANA time zone.") from exc
        return value

    @field_validator("payment_methods")
    @classmethod
    def clean_payment_methods(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 40 for value in cleaned):
            raise ValueError("Payment methods must contain 1 to 40 characters.")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("Payment methods must be unique.")
        return cleaned
