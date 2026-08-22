from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship
from app.models.base import Base

class Brand(Base):
    __tablename__ = "brands"
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    logo = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    products = relationship("Product", back_populates="brand")
