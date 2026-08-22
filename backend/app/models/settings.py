import json
from sqlalchemy import Boolean, Column, String, Text
from app.models.base import Base

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=False, nullable=False)

    @property
    def value_dict(self) -> dict:
        try:
            return json.loads(self.value) if self.value else {}
        except (json.JSONDecodeError, TypeError):
            return {}
