from sqlalchemy.orm import DeclarativeBase, declared_attr
import re


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        # Convert CamelCase class name to snake_case table name automatically.
        name = cls.__name__
        name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
        return name.lower() + "s"
