"""Database configuration and session management"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

# Check if using async or sync
is_async = settings.DATABASE_URL.startswith("postgresql+asyncpg://")
AsyncSessionLocal = None

if is_async:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=0,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
        pool_pre_ping=True,
    )

Base = declarative_base()


async def get_db():
    """Dependency for getting database session"""
    if is_async:
        async with AsyncSessionLocal() as session:
            yield session
    else:
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
