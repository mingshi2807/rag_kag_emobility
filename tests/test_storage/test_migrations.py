"""Database migration runner tests."""

from __future__ import annotations

import uuid

import asyncpg

from rag_ocpp.storage.migrations import MigrationRunner


async def _fresh_database(postgres_container) -> tuple[str, str]:
    db_name = f"mig_{uuid.uuid4().hex}"
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    admin_dsn = f"postgresql://test:test@{host}:{port}/test_rag"
    db_dsn = f"postgresql://test:test@{host}:{port}/{db_name}"

    admin = await asyncpg.connect(dsn=admin_dsn)
    await admin.execute(f'CREATE DATABASE "{db_name}"')
    await admin.close()

    return admin_dsn, db_dsn


async def _drop_database(admin_dsn: str, db_name: str) -> None:
    admin = await asyncpg.connect(dsn=admin_dsn)
    await admin.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1
        """,
        db_name,
    )
    await admin.execute(f'DROP DATABASE "{db_name}"')
    await admin.close()


async def test_migrations_apply_to_fresh_database(postgres_container):
    admin_dsn, db_dsn = await _fresh_database(postgres_container)
    db_name = db_dsn.rsplit("/", maxsplit=1)[-1]

    pool = await asyncpg.create_pool(dsn=db_dsn, min_size=1, max_size=2)
    try:
        runner = MigrationRunner(pool)

        result = await runner.apply()
        statuses = await runner.status()
        second = await runner.apply()

        table_rows = await pool.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                'documents',
                'chunks',
                'audit_events',
                'schema_migrations'
              )
            ORDER BY table_name
            """
        )
    finally:
        await pool.close()
        await _drop_database(admin_dsn, db_name)

    assert [migration.version for migration in result.applied] == ["001", "002"]
    assert second.applied == []
    assert [status.version for status in statuses] == ["001", "002"]
    assert all(status.applied for status in statuses)
    assert {row["table_name"] for row in table_rows} == {
        "audit_events",
        "chunks",
        "documents",
        "schema_migrations",
    }


async def test_migrations_can_baseline_existing_schema(postgres_container):
    admin_dsn, db_dsn = await _fresh_database(postgres_container)
    db_name = db_dsn.rsplit("/", maxsplit=1)[-1]

    pool = await asyncpg.create_pool(dsn=db_dsn, min_size=1, max_size=2)
    try:
        runner = MigrationRunner(pool)
        initial_migration = runner.discover()[0]

        async with pool.acquire() as conn:
            await conn.execute(initial_migration.sql)
            await conn.execute("DROP TABLE audit_events")

        baseline = await runner.baseline()
        pending_after_baseline = await runner.status()
        result = await runner.apply()
        statuses = await runner.status()
    finally:
        await pool.close()
        await _drop_database(admin_dsn, db_name)

    assert [migration.version for migration in baseline.applied] == ["001"]
    assert [status.version for status in pending_after_baseline if not status.applied] == ["002"]
    assert [migration.version for migration in result.applied] == ["002"]
    assert [status.version for status in statuses] == ["001", "002"]
    assert all(status.applied for status in statuses)
