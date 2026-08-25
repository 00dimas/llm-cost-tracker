from __future__ import annotations

import asyncio
from importlib.resources import files

import asyncpg

from .config import Settings
from .pricing import PriceCatalog


async def migrate(database_url: str) -> None:
    connection = await asyncpg.connect(database_url)
    try:
        sql = files("llm_cost_tracker").joinpath(
            "migrations/001_initial.sql"
        ).read_text(encoding="utf-8")
        async with connection.transaction():
            await connection.execute(sql)
            catalog = PriceCatalog.load()
            await connection.executemany(
                """
                INSERT INTO model_pricing (
                    provider, model, input_price_per_million,
                    output_price_per_million, source_url, updated_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (provider, model) DO UPDATE SET
                    input_price_per_million = EXCLUDED.input_price_per_million,
                    output_price_per_million = EXCLUDED.output_price_per_million,
                    source_url = EXCLUDED.source_url,
                    updated_at = NOW()
                """,
                [
                    (
                        price.provider,
                        price.model,
                        price.input_price,
                        price.output_price,
                        price.source_url,
                    )
                    for price in catalog.prices
                ],
            )
    finally:
        await connection.close()


def main() -> None:
    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required")
    asyncio.run(migrate(settings.database_url))
    print("Database migration and pricing sync completed")


if __name__ == "__main__":
    main()
