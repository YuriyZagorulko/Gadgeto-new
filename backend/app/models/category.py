from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.base import Base, main_metadata


class Category(Base):
    __tablename__ = "categories"
    
    legacy_id = Column(Integer, nullable=True, index=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    seo_focus_keyphrase = Column(String(255), nullable=True)
    image = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    
    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("ProductCategory", back_populates="category")
    filters = relationship("CategoryFilter", back_populates="category")


# CategoryClosure must be registered with main_metadata
from sqlalchemy import Table as SATable
closure_table = SATable(
    "category_closure",
    main_metadata,
    Column("ancestor_id", Integer, ForeignKey("categories.id"), primary_key=True),
    Column("descendant_id", Integer, ForeignKey("categories.id"), primary_key=True),
    Column("path_length", Integer, nullable=False),
)
