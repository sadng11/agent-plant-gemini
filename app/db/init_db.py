"""
CLI / Script utility for database schema initialization and migrations.

Usage:
    python -m app.db.init_db
    python -m app.db.init_db --drop
"""

import argparse
import asyncio
import sys
import logging
from sqlalchemy import text

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine, init_db, drop_db
import app.models.db_models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("phytoagent.db_init")


async def main() -> None:
    parser = argparse.ArgumentParser(description="PhytoAgent Database Initialization & Migration Tool")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all existing tables before creating schema",
    )
    args = parser.parse_args()

    # Mask password for secure logging
    db_url_safe = str(settings.DATABASE_URL).split("@")[-1] if "@" in str(settings.DATABASE_URL) else str(settings.DATABASE_URL)
    logger.info(f"Target Database Host/Database: {db_url_safe}")
    logger.info(f"Models to register: {list(Base.metadata.tables.keys())}")

    try:
        # Test connection first
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
        logger.info("Successfully connected to the database server.")

        if args.drop:
            logger.warning("Dropping all existing database tables...")
            await drop_db()
            logger.info("Existing database tables dropped.")

        logger.info("Creating all missing tables and indexes...")
        await init_db()
        logger.info("✅ Database schema initialized successfully!")
        logger.info(f"Tables present in metadata: {', '.join(Base.metadata.tables.keys())}")

    except Exception as exc:
        logger.error(f"❌ Database initialization failed: {exc}", exc_info=True)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
