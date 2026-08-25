"""Channel mapping models (Internal → External Channel).

Direction:
  Internal Category    → External Channel Category
  Internal Attribute   → External Channel Attribute   (optionally scoped by external category)
  Internal Value       → External Channel Value       (optionally scoped by external category)

Internal attributes remain global and category-independent; the optional
category_external_id on mapping tables exists only on the channel side.
"""

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class ChannelCategoryMapping(Base):
    __tablename__ = "channel_category_mappings"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    internal_category_id = Column(
        Integer, ForeignKey("categories.id"), nullable=False, index=True,
    )
    external_category_id = Column(String(255), nullable=True)
    external_category_name = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="proposed")  # proposed | accepted | excluded
    confidence = Column(Float, nullable=True)
    source = Column(String(20), nullable=False, default="manual")  # manual | auto
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    channel = relationship("Channel")

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "internal_category_id",
            name="uq_channel_cat_mapping",
        ),
    )


class ChannelAttributeMapping(Base):
    __tablename__ = "channel_attribute_mappings"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    internal_attribute_id = Column(
        Integer, ForeignKey("attributes.id"), nullable=False, index=True,
    )
    external_attribute_id = Column(String(255), nullable=True)
    external_attribute_name = Column(String(500), nullable=True)
    # Rozetka may require a category scope for the attribute mapping.
    external_category_id = Column(String(255), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="proposed")
    confidence = Column(Float, nullable=True)
    source = Column(String(20), nullable=False, default="manual")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    channel = relationship("Channel")

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "internal_attribute_id",
            "external_category_id",
            name="uq_channel_attr_mapping",
        ),
    )


class ChannelValueMapping(Base):
    __tablename__ = "channel_value_mappings"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    internal_value_id = Column(
        Integer, ForeignKey("attribute_values.id"), nullable=False, index=True,
    )
    external_value_id = Column(String(255), nullable=True)
    external_value_name = Column(String(500), nullable=True)
    external_category_id = Column(String(255), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="proposed")
    confidence = Column(Float, nullable=True)
    source = Column(String(20), nullable=False, default="manual")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    channel = relationship("Channel")

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "internal_value_id",
            "external_category_id",
            name="uq_channel_val_mapping",
        ),
    )