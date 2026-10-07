"""Request and response models for store records."""

import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, field_validator

HOURS_PATTERN = re.compile(
    r"(?i)^(?:(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d|closed)$"
)


class Category(str, Enum):
    GROCERY = "grocery"
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    PHARMACY = "pharmacy"
    HARDWARE = "hardware"
    BOOKSTORE = "bookstore"
    RESTAURANT = "restaurant"
    CONVENIENCE = "convenience"
    OTHER = "other"


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _validate_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        raise ValueError("must contain 7 to 15 digits")
    if re.fullmatch(r"\+?[0-9\s().-]+", value) is None:
        raise ValueError("contains invalid characters")
    return value


class Address(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    street: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str = Field(min_length=2, max_length=100)

    @field_validator("state", "postal_code", mode="before")
    @classmethod
    def blank_optional(cls, value: object) -> object:
        return _blank_to_none(value)


class OpeningHours(BaseModel):
    """Daily hours as HH:MM-HH:MM, or the word closed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    monday: str | None = None
    tuesday: str | None = None
    wednesday: str | None = None
    thursday: str | None = None
    friday: str | None = None
    saturday: str | None = None
    sunday: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_day(cls, value: object) -> object:
        value = _blank_to_none(value)
        if isinstance(value, str) and value.strip().casefold() == "closed":
            return "closed"
        return value

    @field_validator("*")
    @classmethod
    def check_day(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if HOURS_PATTERN.fullmatch(value) is None:
            raise ValueError("must be HH:MM-HH:MM or 'closed'")
        return value


class StoreCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "Harbor Market",
                    "description": "Neighborhood grocery with fresh produce and a bakery.",
                    "address": {
                        "street": "120 Market Street",
                        "city": "San Francisco",
                        "state": "CA",
                        "postal_code": "94105",
                        "country": "USA",
                    },
                    "phone": "+1 415 555 0148",
                    "email": "hello@example.com",
                    "website": "https://example.com/harbor",
                    "category": "grocery",
                    "is_active": True,
                    "opening_hours": {
                        "monday": "08:00-21:00",
                        "tuesday": "08:00-21:00",
                        "wednesday": "08:00-21:00",
                        "thursday": "08:00-21:00",
                        "friday": "08:00-21:00",
                        "saturday": "09:00-20:00",
                        "sunday": "10:00-18:00",
                    },
                }
            ]
        },
    )

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    address: Address
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    website: AnyHttpUrl | None = None
    category: Category
    is_active: bool = True
    opening_hours: OpeningHours | None = None

    @field_validator("description", "phone", "email", "website", mode="before")
    @classmethod
    def blank_optional(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class StoreUpdate(BaseModel):
    """Partial update. Omitted fields stay as they are.

    address and opening_hours, when sent, replace the whole nested object.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    address: Address | None = None
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    website: AnyHttpUrl | None = None
    category: Category | None = None
    is_active: bool | None = None
    opening_hours: OpeningHours | None = None

    @field_validator("description", "phone", "email", "website", mode="before")
    @classmethod
    def blank_optional(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class Store(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    description: str | None = None
    address: Address
    phone: str | None = None
    email: EmailStr | None = None
    website: AnyHttpUrl | None = None
    category: Category
    is_active: bool
    opening_hours: OpeningHours | None = None
    created_at: datetime
    updated_at: datetime


class StoreList(BaseModel):
    items: list[Store]
    total: int
    skip: int
    limit: int


StoreId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
