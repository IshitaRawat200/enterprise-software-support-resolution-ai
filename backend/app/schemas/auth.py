from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=255,
    )

    company_name: str = Field(
        min_length=2,
        max_length=255,
    )

    email: str = Field(
        min_length=5,
        max_length=255,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    confirm_password: str = Field(
        min_length=8,
        max_length=128,
    )

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")

        return self


class LoginRequest(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=255,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CustomerRegistrationResponse(BaseModel):
    user: UserResponse
    customer_id: UUID
    full_name: str
    company_name: str