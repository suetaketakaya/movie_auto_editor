"""
SQLAlchemy async database setup.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


def get_async_engine(database_url: str):
    """Create async SQLAlchemy engine."""
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def get_async_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    engine = get_async_engine(database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
