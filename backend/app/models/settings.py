"""
Settings model.
"""

from sqlalchemy import Boolean, Column, String, Text

from app.models.base import Base


class Setting(Base):
    """Application setting."""
    __tablename__ = "settings"

    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=False, nullable=False)

    @property
    def value_dict(self) -> dict:
        """Parse JSON value if possible."""
        import json
        if self.value:
            try:
                return json.loads(self.value)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
