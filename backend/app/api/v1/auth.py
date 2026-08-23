"""
Customer authentication API (separate from admin auth).

Provides registration with email verification, login, logout, and profile.
"""
import asyncio
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.core.ratelimit import rate_limiter
from app.models.user import User, UserStatus, UserRole
from app.models.session import UserSession
from app.services.email import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic Schemas


class RegisterRequest(BaseModel):
    email: str
    password: str
    confirm_password: str
    full_name: str
    phone: str = ""

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name is required")
        if len(v) < 2:
            raise ValueError("full_name too short")
        if len(v) > 255:
            raise ValueError("full_name too long")
        if not re.match(r"^[A-Za-z0-9А-ЩЬЮЯҐЇІЄа-щьюяґїіє'`\-\.\s]+$", v):
            raise ValueError("full_name contains invalid characters")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("email is required")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("invalid email format")
        if ".." in v:
            raise ValueError("invalid email format")
        if v.count("@") != 1:
            raise ValueError("invalid email format")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return ""
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^(\+?380\d{9}|0\d{9})$", cleaned):
            raise ValueError("invalid phone format")
        if cleaned.startswith("0"):
            cleaned = "+38" + cleaned
        elif cleaned.startswith("380"):
            cleaned = "+" + cleaned
        elif not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("password is required")
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("password too long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("password must contain at least one digit")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        """Prevent bcrypt DoS by limiting password length."""
        if v and len(v) > 128:
            raise ValueError("password too long")
        return v


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("email is required")
        return v


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserProfile(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    status: str
    email_verified: bool
    email_verified_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("email is required")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("invalid email format")
        if ".." in v:
            raise ValueError("invalid email format")
        if v.count("@") != 1:
            raise ValueError("invalid email format")
        return v


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("password is required")
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("password too long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("password must contain at least one digit")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self



# Helpers


def _generate_verification_token() -> tuple[str, str, datetime]:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(hours=24)
    return raw_token, token_hash, expires_at


async def _get_user_by_token(db: AsyncSession, token: str) -> Optional[User]:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(User).where(
            User.verification_token_hash == token_hash,
            User.verification_token_expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


async def _get_user_from_bearer_token(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Необхідна автентифікація")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Необхідна автентифікація")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(User).join(UserSession, UserSession.user_id == User.id).where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > datetime.utcnow(),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Сесію не знайдено або термін її дії закінчився",
        )
    return user


# Endpoints


@router.post("/register", response_model=MessageResponse)
async def register(
    req: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Register a new customer account.

    Rate-limited: max 5 registrations per IP per 60 seconds.
    """
    rate_limiter.check(
        rate_limiter._get_key(request, "register"),
        max_requests=5,
        window_seconds=60,
    )

    result = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(req.email))
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        if existing_user.email_verified_at:
            raise HTTPException(
                status_code=409,
                detail="Користувач з такою електронною поштою вже існує.",
            )
        raise HTTPException(
            status_code=409,
            detail="EMAIL_EXISTS_UNVERIFIED",
        )

    if req.phone:
        phone_result = await db.execute(
            select(User).where(User.phone == req.phone)
        )
        if phone_result.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="Користувач з таким номером телефону вже існує.",
            )

    raw_token, token_hash, expires_at = _generate_verification_token()

    user = User(
        email=req.email,
        password_hash=get_password_hash(req.password),
        full_name=req.full_name,
        phone=req.phone,
        role=UserRole.CUSTOMER.value,
        status=UserStatus.PENDING.value,
        verification_token_hash=token_hash,
        verification_token_expires_at=expires_at,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    try:
        email_sent = await send_verification_email(
            to_email=user.email,
            to_name=user.full_name or user.email,
            verification_url=verification_url,
        )
    except Exception as e:
        logger.error(
            "Exception sending verification email for user %d (%s): %s",
            user.id, user.email, e,
        )
        email_sent = False

    if not email_sent:
        logger.warning(
            "Failed to send verification email for user %d (%s). User created.",
            user.id, user.email,
        )
        return MessageResponse(
            message="РЕЄСТРАЦІЯ_УСПІШНА_АЛЕ_EMAIL_НЕ_ВІДПРАВЛЕНО"
        )

    return MessageResponse(
        message=f"Перевірте свою електронну пошту. Ми надіслали лист на {user.email}."
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    req: VerifyEmailRequest,
    db: AsyncSession = Depends(get_session),
):
    """Verify email address using a verification token."""
    if not req.token or len(req.token) < 10:
        raise HTTPException(
            status_code=400, detail="Недійсне посилання для підтвердження."
        )

    user = await _get_user_by_token(db, req.token)
    if not user:
        token_hash = hashlib.sha256(req.token.encode()).hexdigest()
        expired_result = await db.execute(
            select(User).where(User.verification_token_hash == token_hash)
        )
        expired_user = expired_result.scalar_one_or_none()
        if expired_user:
            raise HTTPException(
                status_code=410,
                detail="Посилання на підтвердження застаріло.",
            )
        raise HTTPException(
            status_code=404,
            detail="Недійсне посилання для підтвердження.",
        )

    if user.email_verified_at:
        raise HTTPException(
            status_code=400,
            detail="Електронну пошту вже підтверджено.",
        )

    user.email_verified_at = datetime.utcnow()
    user.status = UserStatus.ACTIVE.value
    user.verification_token_hash = None
    user.verification_token_expires_at = None
    await db.commit()

    logger.info("User %d (%s) verified email successfully", user.id, user.email)
    return MessageResponse(message="Email підтверджено. Ваш акаунт успішно активовано.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    req: ResendVerificationRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Resend verification email to an unverified user.

    Rate-limited: strict 60-second cooldown per IP+email combination.
    """
    rl_key = rate_limiter._get_key(request, f"resend:{req.email}")
    rate_limiter.check(rl_key, cooldown_seconds=60)

    result = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(req.email))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Користувача з такою електронною поштою не знайдено.",
        )
    if user.email_verified_at:
        raise HTTPException(
            status_code=400,
            detail="Електронну пошту вже підтверджено.",
        )

    raw_token, token_hash, expires_at = _generate_verification_token()
    user.verification_token_hash = token_hash
    user.verification_token_expires_at = expires_at
    await db.commit()

    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    try:
        email_sent = await send_verification_email(
            to_email=user.email,
            to_name=user.full_name or user.email,
            verification_url=verification_url,
        )
    except Exception as e:
        logger.error(
            "Exception resending verification email for user %d (%s): %s",
            user.id, user.email, e,
        )
        email_sent = False

    if not email_sent:
        raise HTTPException(
            status_code=500,
            detail="Не вдалося відправити лист для підтвердження. Спробуйте ще раз.",
        )

    return MessageResponse(
        message=f"Лист для підтвердження надіслано на {user.email}."
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Authenticate user with email and password.

    Rate-limited: max 10 login attempts per IP per 60 seconds.
    """
    rate_limiter.check(
        rate_limiter._get_key(request, "login"),
        max_requests=10,
        window_seconds=60,
    )

    result = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(req.email.strip()))
    )
    user = result.scalar_one_or_none()

    # Use constant-time comparison via bcrypt, but first verify user exists
    # to prevent timing attacks on email enumeration
    if not user:
        # Fake hash verification to prevent timing-based email enumeration
        verify_password("dummy_fake_password_long_enough_123", "$2b$12$" + "x" * 53)
        raise HTTPException(
            status_code=401,
            detail="Невірна електронна пошта або пароль.",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Невірна електронна пошта або пароль.",
        )

    if user.status == UserStatus.BANNED.value:
        raise HTTPException(
            status_code=403,
            detail="Обліковий запис заблоковано. Зверніться до підтримки.",
        )
    if user.status == UserStatus.INACTIVE.value:
        raise HTTPException(
            status_code=403,
            detail="Обліковий запис деактивовано.",
        )
    if not user.email_verified_at:
        raise HTTPException(
            status_code=403,
            detail="EMAIL_NOT_VERIFIED",
        )

    token = secrets.token_urlsafe(32)
    token_hash_val = hashlib.sha256(token.encode()).hexdigest()
    session = UserSession(
        token_hash=token_hash_val,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(session)

    user.last_login_at = datetime.utcnow()
    user.login_count = (user.login_count or 0) + 1
    await db.commit()

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
        },
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_session),
):
    """Invalidate the current session token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Необхідна автентифікація")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Необхідна автентифікація")

    token_hash_val = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash_val)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()
    return MessageResponse(message="Ви успішно вийшли з акаунту.")


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(_get_user_from_bearer_token)):
    """Return the authenticated user's profile."""
    return UserProfile(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        status=user.status,
        email_verified=user.email_verified_at is not None,
        email_verified_at=user.email_verified_at,
    )





@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Request a password reset email.

    Rate-limited: strict 60-second cooldown per IP+email combination.
    Always returns the same response regardless of whether the email exists.
    """
    rl_key = rate_limiter._get_key(request, f"forgot:{req.email}")
    rate_limiter.check(rl_key, cooldown_seconds=60)

    # Always use the same generic message
    generic_message = (
        "Якщо обліковий запис із цією електронною поштою існує, "
        "ми надіслали посилання для відновлення пароля."
    )

    result = await db.execute(
        select(User).where(func.lower(User.email) == func.lower(req.email))
    )
    user = result.scalar_one_or_none()

    if user:
        # Generate secure reset token (48 bytes raw -> 64 chars URL-safe)
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(hours=1)

        user.password_reset_token_hash = token_hash
        user.password_reset_token_expires_at = expires_at
        await db.commit()

        # Build reset URL
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

        try:
            email_sent = await send_password_reset_email(
                to_email=user.email,
                to_name=user.full_name or user.email,
                reset_url=reset_url,
            )
        except Exception as e:
            logger.error(
                "Exception sending password reset email for user %d (%s): %s",
                user.id, user.email, e,
            )
            email_sent = False

        if not email_sent:
            logger.warning(
                "Failed to send password reset email for user %d (%s).",
                user.id, user.email,
            )
    else:
        # Prevent timing-based enumeration by performing a dummy operation
        await asyncio.sleep(0.05)

    return ForgotPasswordResponse(message=generic_message)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Reset password using a reset token.

    Rate-limited: max 5 attempts per IP per 60 seconds.
    """
    rate_limiter.check(
        rate_limiter._get_key(request, "reset-password"),
        max_requests=5,
        window_seconds=60,
    )

    if not req.token or len(req.token) < 10:
        raise HTTPException(
            status_code=400,
            detail="Недійсне або застаріле посилання для відновлення пароля.",
        )

    token_hash = hashlib.sha256(req.token.encode()).hexdigest()

    # Find user with this reset token hash
    result = await db.execute(
        select(User).where(User.password_reset_token_hash == token_hash)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Посилання для відновлення пароля недійсне або застаріло.",
        )

    # Check expiration
    if (user.password_reset_token_expires_at is None
            or user.password_reset_token_expires_at < datetime.utcnow()):
        # Clean up expired token
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Посилання для відновлення пароля недійсне або застаріло.",
        )

    # Hash new password
    new_password_hash = get_password_hash(req.password)

    # Update user password
    user.password_hash = new_password_hash

    # Invalidate reset token immediately (single-use)
    user.password_reset_token_hash = None
    user.password_reset_token_expires_at = None

    # Invalidate all existing sessions for this user
    await db.execute(
        delete(UserSession).where(UserSession.user_id == user.id)
    )

    await db.commit()

    logger.info(
        "Password reset successful for user %d (%s). All sessions revoked.",
        user.id, user.email,
    )

    return MessageResponse(
        message="Пароль успішно змінено."
    )


@router.get("/me/raw")

async def me_raw(user: User = Depends(_get_user_from_bearer_token)):
    """Return the raw user dict (backward compatibility for Header/footer)."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "status": user.status,
        "email_verified": user.email_verified_at is not None,
    }
