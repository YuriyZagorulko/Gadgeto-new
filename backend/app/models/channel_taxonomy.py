"""Rozetka (channel) taxonomy / reference data models.

These tables store a local copy of the marketplace's category, attribute, and
permissible-value dictionaries — fetched from the official Seller API during
a "refresh taxonomy" operation.

Rozetka attributes are category-specific, so channel_external_attributes
carries a category_external_id FK to enable the correct scope.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class ChannelExternalCategory(Base):
    """A category from the external marketplace taxonomy (e.g. Rozetka)."""

    __tablename__ = "channel_external_categories"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    external_id = Column(String(255), nullable=False, index=True)
    parent_external_id = Column(String(255), nullable=True, index=True)
    name = Column(String(500), nullable=False)
    path = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)
    fetched_at = Column(DateTime, nullable=True)

    channel = relationship("Channel")

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "external_id",
            name="uq_channel_ext_category",
        ),
    )


class ChannelExternalAttribute(Base):
    """An attribute (characteristic) defined by the marketplace for a specific
    category.  Many marketplace attributes are category-scoped, so the FK to
    category_external_id is required."""

    __tablename__ = "channel_external_attributes"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    category_external_id = Column(
        String(255), nullable=False, index=True,
    )
    external_id = Column(String(255), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    # e.g. select | text | number | boolean | multi
    param_type = Column(String(50), nullable=True)
    is_required = Column(Integer, default=0, nullable=False)
    unit = Column(String(100), nullable=True)
    raw_json = Column(Text, nullable=True)
    fetched_at = Column(DateTime, nullable=True)

    channel = relationship("Channel")

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "category_external_id", "external_id",
            name="uq_channel_ext_attribute",
        ),
    )


class ChannelExternalValue(Base):
    """Permissible value for a marketplace attribute (when param_type is
    'select' or similar).  Rozetka uses integer IDs for values."""

    __tablename__ = "channel_external_values"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    attribute_external_id = Column(String(255), nullable=False, index=True)
    external_id = Column(String(255), nullable=True, index=True)
    value = Column(String(500), nullable=False)
    raw_json = Column(Text, nullable=True)
    fetched_at = Column(DateTime, nullable=True)

    channel = relationship("Channel")

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "attribute_external_id", "value",
            name="uq_channel_ext_value",
        ),
    )