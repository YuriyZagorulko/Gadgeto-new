"""
Public and authenticated product reviews API.

Endpoints:
- GET  /products/{product_id}/reviews — public, approved reviews only
- POST /products/{product_id}/reviews — authenticated, creates pending review
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.product import Product, ProductReview, ReviewStatus
from app.models.user import User
from app.api.v1.auth import _get_user_from_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic Schemas ──

class ReviewCreateRequest(BaseModel):
    rating: int
    text: str

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if not isinstance(v, int) or v < 1 or v > 5:
            raise ValueError("Оцінка має бути від 1 до 5")
        return v

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Текст відгуку обов'язковий")
        if len(v) > 5000:
            raise ValueError("Текст відгуку занадто довгий (максимум 5000 символів)")
        return v


class ReviewAuthorResponse(BaseModel):
    name: str


class ReviewResponse(BaseModel):
    id: int
    rating: int
    text: str
    author: ReviewAuthorResponse
    created_at: datetime
    verified_purchase: bool = False


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int


class ReviewStatsResponse(BaseModel):
    average_rating: float
    total_reviews: int
    rating_distribution: dict[int, int]


class MessageResponse(BaseModel):
    message: str


# ── Public: list approved reviews ──

@router.get("/products/{product_id}/reviews", response_model=ReviewListResponse)
async def list_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    session: AsyncSession = Depends(get_session),
):
    """List approved reviews for a product. Public endpoint."""
    # Verify product exists
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не знайдено")

    offset = (page - 1) * page_size

    # Fetch approved reviews with user info
    result = await session.execute(
        select(ProductReview, User.full_name)
        .outerjoin(User, ProductReview.user_id == User.id)
        .where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.status == ReviewStatus.APPROVED,
            )
        )
        .order_by(ProductReview.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    # Count total approved reviews
    count_result = await session.execute(
        select(func.count(ProductReview.id))
        .where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.status == ReviewStatus.APPROVED,
            )
        )
    )
    total = count_result.scalar_one()

    items = []
    for review, user_full_name in rows:
        author_name = user_full_name or review.author_name or "Покупець"
        items.append(
            ReviewResponse(
                id=review.id,
                rating=review.rating,
                text=review.content or "",
                author=ReviewAuthorResponse(name=author_name),
                created_at=review.created_at,
            )
        )

    return ReviewListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Public: get review statistics ──

@router.get("/products/{product_id}/reviews/stats", response_model=ReviewStatsResponse)
async def get_review_stats(
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get rating statistics for a product. Public endpoint, approved reviews only."""
    # Verify product exists
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не знайдено")

    # Calculate average and distribution
    result = await session.execute(
        select(
            func.avg(ProductReview.rating).label("avg_rating"),
            func.count(ProductReview.id).label("total"),
        )
        .where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.status == ReviewStatus.APPROVED,
            )
        )
    )
    row = result.one()
    avg_rating = float(row.avg_rating) if row.avg_rating else 0.0
    total = row.total

    # Rating distribution
    dist_result = await session.execute(
        select(ProductReview.rating, func.count(ProductReview.id))
        .where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.status == ReviewStatus.APPROVED,
            )
        )
        .group_by(ProductReview.rating)
    )
    distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for rating, count in dist_result.all():
        distribution[rating] = count

    return ReviewStatsResponse(
        average_rating=round(avg_rating, 1),
        total_reviews=total,
        rating_distribution=distribution,
    )
    return ReviewStatsResponse(
        average_rating=round(avg_rating, 1),
        total_reviews=total,
        rating_distribution=distribution,
    )


# ── Authenticated: create review ──

@router.post("/products/{product_id}/reviews", response_model=MessageResponse)
async def create_review(
    product_id: int,
    data: ReviewCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(_get_user_from_bearer_token),
):
    """Create a new review. Authenticated users only. Review starts as PENDING."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Необхідна автентифікація")

    # Verify product exists
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не знайдено")

    # Check for existing review by this user for this product
    existing = await session.execute(
        select(ProductReview).where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.user_id == current_user.id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Ви вже залишили відгук на цей товар",
        )

    # Create review (always PENDING, never trust client for status)
    review = ProductReview(
        product_id=product_id,
        user_id=current_user.id,
        author_name=current_user.full_name or current_user.email,
        author_email=current_user.email,
        rating=data.rating,
        content=data.text,
        status=ReviewStatus.PENDING,
    )
    session.add(review)
    await session.commit()

    logger.info(
        "User %d created review for product %d (status: PENDING)",
        current_user.id,
        product_id,
    )

    return MessageResponse(message="Ваш відгук надіслано на модерацію.")


# ── Authenticated: get user's own review for a product ──

@router.get("/products/{product_id}/reviews/me")
async def get_my_review(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(_get_user_from_bearer_token),
):
    """Get the current user's review for a product (if any)."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Необхідна автентифікація")

    result = await session.execute(
        select(ProductReview).where(
            and_(
                ProductReview.product_id == product_id,
                ProductReview.user_id == current_user.id,
            )
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        return None

    return {
        "id": review.id,
        "rating": review.rating,
        "text": review.content or "",
        "status": review.status,
        "created_at": review.created_at,
    }


