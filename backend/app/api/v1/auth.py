"""
Authentication API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.database import get_session
from app.repositories.user import UserRepository
from app.core.security import verify_password, create_access_token

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """Login and get access token."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(form_data.username)

    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(access_token=access_token)


@router.post("/register")
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user."""
    user_repo = UserRepository(session)

    # Check if email already exists
    existing = await user_repo.get_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = user_repo.model_class(
        email=request.email,
        full_name=request.full_name,
    )
    user.set_password(request.password)

    await user_repo.create(user)

    return {"message": "User registered successfully"}


@router.get("/me")
async def get_current_user():
    """Get current user info (requires auth)."""
    # Will be implemented with Depends(get_current_user)
    raise HTTPException(status_code=401, detail="Not implemented")
