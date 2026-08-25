from __future__ import annotations

import argparse
import asyncio
import uuid

import asyncpg

from .config import Settings
from .tenancy import generate_api_key, hash_api_key


async def create_tenant(
    database_url: str, slug: str, name: str, key_name: str
) -> str:
    api_key = generate_api_key()
    connection = await asyncpg.connect(database_url)
    try:
        async with connection.transaction():
            tenant_id = uuid.uuid4()
            await connection.execute(
                "INSERT INTO tenants (id, slug, name) VALUES ($1, $2, $3)",
                tenant_id,
                slug,
                name,
            )
            await connection.execute(
                """
                INSERT INTO tenant_api_keys (
                    id, tenant_id, name, key_prefix, key_hash
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                uuid.uuid4(),
                tenant_id,
                key_name,
                api_key[:12],
                hash_api_key(api_key),
            )
    finally:
        await connection.close()
    return api_key


async def revoke_api_key(database_url: str, slug: str, key_name: str) -> bool:
    connection = await asyncpg.connect(database_url)
    try:
        result = await connection.execute(
            """
            UPDATE tenant_api_keys
            SET revoked_at = NOW()
            FROM tenants
            WHERE tenants.id = tenant_api_keys.tenant_id
              AND tenants.slug = $1
              AND tenant_api_keys.name = $2
              AND tenant_api_keys.revoked_at IS NULL
            """,
            slug,
            key_name,
        )
        return result == "UPDATE 1"
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage LLM Cost Tracker tenants")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create", help="Create tenant and API key")
    create_parser.add_argument("--slug", required=True)
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--key-name", default="default")
    revoke_parser = subparsers.add_parser("revoke", help="Revoke a tenant API key")
    revoke_parser.add_argument("--slug", required=True)
    revoke_parser.add_argument("--key-name", required=True)
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required")
    if args.command == "create":
        api_key = asyncio.run(
            create_tenant(settings.database_url, args.slug, args.name, args.key_name)
        )
        print("Tenant created. Store this API key now; it cannot be recovered:")
        print(api_key)
    elif not asyncio.run(
        revoke_api_key(settings.database_url, args.slug, args.key_name)
    ):
        raise SystemExit("Active tenant API key was not found")
    else:
        print("Tenant API key revoked")


if __name__ == "__main__":
    main()
