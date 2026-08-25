"""Channel publication foundation models.

The internal catalog (products, categories, attributes, ...) remains the
single Source of Truth.  These tables describe only the *publication* of
catalog products onto external marketplaces ("channels", e.g. Rozetka).

Design rules (Phase 1):
  - No marketplace-specific columns are added to catalog tables.
  - Direction of future mapping is Internal → Channel and uses separate
    channel_* tables; the supplier importer mappings are untouched.
  - Listing state is split into two independent axes:
      publication_status — what the admin intends (disabled/draft/ready/published)
      sync_status        — how the last engine attempt ended (idle/syncing/success/error)
    `remote_status` keeps whatever the marketplace itself reports.
"""

from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class PublicationStatus(str, Enum):
    """Admin-side intent for a product on a channel."""

    DISABLED = "disabled"
    DRAFT = "draft"
    READY = "ready"
    PUBLISHED = "published"


class ChannelSyncStatus(str, Enum):
    """Outcome of the last synchronization attempt for a listing."""

    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR = "error"


class Channel(Base):
    __tablename__ = "channels"

    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_enabled = Column(Boolean, default=False, nullable=False)
    adapter_config_json = Column(Text, nullable=True)

    settings = relationship(
        "ChannelSetting", back_populates="channel", cascade="all, delete-orphan"
    )
    listings = relationship("ChannelListing", back_populates="channel")


class ChannelSetting(Base):
    """Per-channel key/value configuration (follows the `settings` pattern).

    Secrets must be stored with is_secret=TRUE; API endpoints mask them.
    """

    __tablename__ = "channel_settings"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=False, nullable=False)

    channel = relationship("Channel", back_populates="settings")

    __table_args__ = (
        UniqueConstraint("channel_id", "key", name="uq_channel_setting"),
    )


class ChannelListing(Base):
    """A product's publication record on one external channel."""

    __tablename__ = "channel_listings"

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    publication_status = Column(
        SAEnum(PublicationStatus, name="channelpublicationstatus"),
        default=PublicationStatus.DRAFT,
        nullable=False,
    )
    sync_status = Column(
        SAEnum(ChannelSyncStatus, name="channelsyncstatus"),
        default=ChannelSyncStatus.IDLE,
        nullable=False,
    )

    # Stable external identifier returned by the marketplace (e.g. item id).
    external_id = Column(String(255), nullable=True, index=True)

    # Change detection (Phase 6): content vs commercial hashes.
    content_hash = Column(String(64), nullable=True)
    commercial_hash = Column(String(64), nullable=True)

    last_synced_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)

    last_error_type = Column(String(50), nullable=True)
    last_error_message = Column(Text, nullable=True)

    remote_status = Column(String(100), nullable=True)

    product = relationship("Product")
    channel = relationship("Channel", back_populates="listings")
    validation_issues = relationship(
        "ChannelValidationIssue",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("product_id", "channel_id", name="uq_channel_listing"),
        Index(
            "ix_channel_listings_channel_publication",
            "channel_id",
            "publication_status",
        ),
        Index("ix_channel_listings_channel_sync", "channel_id", "sync_status"),
    )


class ChannelValidationIssue(Base):
    """Why a listing cannot be published yet (validation engine fills this in a
    later phase).  One row per issue code per listing."""

    __tablename__ = "channel_validation_issues"

    listing_id = Column(Integer, ForeignKey("channel_listings.id"), nullable=False)
    code = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)

    listing = relationship("ChannelListing", back_populates="validation_issues")

    __table_args__ = (
        # Covers lookups by listing_id as leftmost prefix (PostgreSQL b-tree).
        UniqueConstraint("listing_id", "code", name="uq_channel_validation_issue"),
    )