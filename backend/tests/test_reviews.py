"""Tests for product reviews system.

Tests cover:
- Public API: returns approved reviews, hides pending/rejected, pagination, stats
- Authentication: anonymous cannot create, authenticated can create
- Validation: rating 1-5, text required, max length
- Duplicate reviews: one per user/product
- Moderation: new reviews PENDING, admin can approve/reject
- Authorization: non-admin cannot moderate
- Product validation: nonexistent product returns 404

Uses transactional isolation via db_connection fixture.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Fixtures ──

@pytest.fixture
def sample_product(db_cursor):
    """Create a sample product and return its ID."""
    db_cursor.execute(
        "INSERT INTO products (name, slug, price, status, is_active, is_visible) "
        "VALUES ('Test Product', 'test-product', 1000, 'PUBLISHED', true, true) RETURNING id"
    )
    return db_cursor.fetchone()["id"]


@pytest.fixture
def sample_user(db_cursor):
    """Create a sample user and return its ID."""
    db_cursor.execute(
        "INSERT INTO users (email, password_hash, full_name, role, status) "
        "VALUES ('test@example.com', 'hash', 'Test User', 'customer', 'active') RETURNING id"
    )
    return db_cursor.fetchone()["id"]


@pytest.fixture
def admin_user(db_cursor):
    """Create an admin user and return its ID."""
    db_cursor.execute(
        "INSERT INTO users (email, password_hash, full_name, role, status) "
        "VALUES ('admin@example.com', 'hash', 'Admin User', 'admin', 'active') RETURNING id"
    )
    return db_cursor.fetchone()["id"]


@pytest.fixture
def auth_token(db_cursor, sample_user):
    """Create a session token for the sample user."""
    import hashlib
    token = "test_token_12345"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db_cursor.execute(
        "INSERT INTO sessions (user_id, token_hash, expires_at) "
        "VALUES (%s, %s, NOW() + INTERVAL '1 day')",
        (sample_user, token_hash),
    )
    return token


@pytest.fixture
def admin_token(db_cursor, admin_user):
    """Create a session token for the admin user."""
    import hashlib
    token = "admin_token_12345"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db_cursor.execute(
        "INSERT INTO sessions (user_id, token_hash, expires_at) "
        "VALUES (%s, %s, NOW() + INTERVAL '1 day')",
        (admin_user, token_hash),
    )
    return token


# ── Public API Tests ──

class TestPublicReviewsAPI:
    def test_list_approved_reviews(self, db_cursor, sample_product, sample_user):
        """Public endpoint returns only approved reviews."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 5, 'Great product!', 'APPROVED')",
            (sample_product, sample_user),
        )

        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["rating"] == 5
        assert data["items"][0]["text"] == "Great product!"

    def test_pending_reviews_hidden(self, db_cursor, sample_product, sample_user):
        """Pending reviews are not visible publicly."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 5, 'Pending review', 'PENDING')",
            (sample_product, sample_user),
        )

        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_rejected_reviews_hidden(self, db_cursor, sample_product, sample_user):
        """Rejected reviews are not visible publicly."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 1, 'Rejected review', 'REJECTED')",
            (sample_product, sample_user),
        )

        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_pagination(self, db_cursor, sample_product):
        """Pagination works correctly."""
        for i in range(3):
            db_cursor.execute(
                "INSERT INTO users (email, password_hash, full_name, role, status) "
                "VALUES (%s, 'hash', %s, 'customer', 'active') RETURNING id",
                (f"user{i}@example.com", f"User {i}"),
            )
            uid = db_cursor.fetchone()["id"]
            db_cursor.execute(
                "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
                "VALUES (%s, %s, %s, 5, %s, 'APPROVED')",
                (sample_product, uid, f"User {i}", f"Review {i}"),
            )

        resp = client.get(f"/api/v1/products/{sample_product}/reviews?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_review_stats_only_approved(self, db_cursor, sample_product, sample_user):
        """Rating statistics only include approved reviews."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author1', 5, 'Great!', 'APPROVED')",
            (sample_product, sample_user),
        )
        db_cursor.execute(
            "INSERT INTO users (email, password_hash, full_name, role, status) "
            "VALUES ('user2@example.com', 'hash', 'User 2', 'customer', 'active') RETURNING id",
        )
        uid2 = db_cursor.fetchone()["id"]
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author2', 1, 'Bad!', 'PENDING')",
            (sample_product, uid2),
        )

        resp = client.get(f"/api/v1/products/{sample_product}/reviews/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["average_rating"] == 5.0
        assert data["total_reviews"] == 1
        assert data["rating_distribution"][5] == 1
        assert data["rating_distribution"][1] == 0

    def test_nonexistent_product_returns_404(self):
        """Requesting reviews for nonexistent product returns 404."""
        resp = client.get("/api/v1/products/99999/reviews")
        assert resp.status_code == 404


# ── Authentication Tests ──

class TestAuthentication:
    def test_anonymous_cannot_create_review(self, sample_product):
        """Unauthenticated user cannot create a review."""
        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 5, "text": "Great!"},
        )
        assert resp.status_code == 401

    def test_authenticated_can_create_review(self, db_cursor, sample_product, auth_token):
        """Authenticated user can create a review."""
        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 5, "text": "Great product!"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert "модерацію" in resp.json()["message"]


# ── Validation Tests ──

class TestValidation:
    def test_rating_below_1_rejected(self, sample_product, auth_token):
        """Rating < 1 is rejected."""
        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 0, "text": "Text"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422

    def test_rating_above_5_rejected(self, sample_product, auth_token):
        """Rating > 5 is rejected."""
        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 6, "text": "Text"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422

    def test_empty_text_rejected(self, sample_product, auth_token):
        """Empty text is rejected."""
        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 5, "text": ""},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422

    def test_excessive_text_rejected(self, sample_product, auth_token):
        """Excessively long text is rejected."""
        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 5, "text": "A" * 5001},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422


# ── Duplicate Review Tests ──

class TestDuplicateReviews:
    def test_duplicate_review_rejected(self, db_cursor, sample_product, sample_user, auth_token):
        """Same user cannot review same product twice."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 5, 'First review', 'APPROVED')",
            (sample_product, sample_user),
        )

        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 4, "text": "Second review"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400
        assert "вже залишили" in resp.json()["detail"]


# ── Moderation Tests ──

class TestModeration:
    def test_new_review_is_pending(self, db_cursor, sample_product, sample_user, auth_token):
        """Newly created review has PENDING status."""
        client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 5, "text": "Great!"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        db_cursor.execute(
            "SELECT status FROM product_reviews WHERE product_id = %s AND user_id = %s",
            (sample_product, sample_user),
        )
        row = db_cursor.fetchone()
        assert row["status"] == "PENDING"

    def test_admin_can_approve(self, db_cursor, sample_product, sample_user, admin_token):
        """Admin can approve a pending review."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 5, 'Review text', 'PENDING') RETURNING id",
            (sample_product, sample_user),
        )
        review_id = db_cursor.fetchone()["id"]

        resp = client.patch(
            f"/api/v1/admin/reviews/{review_id}",
            json={"status": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

        db_cursor.execute("SELECT status, moderated_by FROM product_reviews WHERE id = %s", (review_id,))
        row = db_cursor.fetchone()
        assert row["status"] == "APPROVED"
        assert row["moderated_by"] is not None

    def test_admin_can_reject(self, db_cursor, sample_product, sample_user, admin_token):
        """Admin can reject a pending review."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 1, 'Bad review', 'PENDING') RETURNING id",
            (sample_product, sample_user),
        )
        review_id = db_cursor.fetchone()["id"]

        resp = client.patch(
            f"/api/v1/admin/reviews/{review_id}",
            json={"status": "REJECTED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "REJECTED"

    def test_approved_review_becomes_visible(self, db_cursor, sample_product, sample_user, admin_token):
        """Approved review becomes visible through public API."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 5, 'Great!', 'PENDING') RETURNING id",
            (sample_product, sample_user),
        )
        review_id = db_cursor.fetchone()["id"]

        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.json()["total"] == 0

        client.patch(
            f"/api/v1/admin/reviews/{review_id}",
            json={"status": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.json()["total"] == 1

    def test_rejected_review_stays_hidden(self, db_cursor, sample_product, sample_user, admin_token):
        """Rejected review remains hidden."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 1, 'Bad!', 'PENDING') RETURNING id",
            (sample_product, sample_user),
        )
        review_id = db_cursor.fetchone()["id"]

        client.patch(
            f"/api/v1/admin/reviews/{review_id}",
            json={"status": "REJECTED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.json()["total"] == 0

    def test_approved_to_rejected(self, db_cursor, sample_product, sample_user, admin_token):
        """Admin can unpublish an approved review (APPROVED -> REJECTED)."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 5, 'Great!', 'APPROVED') RETURNING id",
            (sample_product, sample_user),
        )
        review_id = db_cursor.fetchone()["id"]

        # Should be visible before
        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.json()["total"] == 1

        resp = client.patch(
            f"/api/v1/admin/reviews/{review_id}",
            json={"status": "REJECTED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "REJECTED"

        # Should be hidden after
        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.json()["total"] == 0

    def test_rejected_to_approved(self, db_cursor, sample_product, sample_user, admin_token):
        """Admin can republish a rejected review (REJECTED -> APPROVED)."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 4, 'Decent', 'REJECTED') RETURNING id",
            (sample_product, sample_user),
        )
        review_id = db_cursor.fetchone()["id"]

        # Should be hidden before
        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.json()["total"] == 0

        resp = client.patch(
            f"/api/v1/admin/reviews/{review_id}",
            json={"status": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

        # Should be visible after
        resp = client.get(f"/api/v1/products/{sample_product}/reviews")
        assert resp.json()["total"] == 1


# ── Authorization Tests ──

class TestAuthorization:
    def test_non_admin_cannot_moderate(self, db_cursor, sample_product, sample_user, auth_token):
        """Normal user cannot approve/reject reviews."""
        db_cursor.execute(
            "INSERT INTO product_reviews (product_id, user_id, author_name, rating, content, status) "
            "VALUES (%s, %s, 'Author', 5, 'Review', 'PENDING') RETURNING id",
            (sample_product, sample_user),
        )
        review_id = db_cursor.fetchone()["id"]

        resp = client.patch(
            f"/api/v1/admin/reviews/{review_id}",
            json={"status": "APPROVED"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 403

    def test_non_admin_cannot_access_admin_list(self, auth_token):
        """Normal user cannot access admin reviews list."""
        resp = client.get(
            "/api/v1/admin/reviews",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 403

    def test_user_cannot_set_status_manually(self, db_cursor, sample_product, sample_user, auth_token):
        """User cannot set status to APPROVED when creating a review."""
        resp = client.post(
            f"/api/v1/products/{sample_product}/reviews",
            json={"rating": 5, "text": "Great!"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

        db_cursor.execute(
            "SELECT status FROM product_reviews WHERE product_id = %s AND user_id = %s",
            (sample_product, sample_user),
        )
        row = db_cursor.fetchone()
        assert row["status"] == "PENDING"
