from sqlalchemy.pool import NullPool

from app.db.session import build_engine_kwargs


def test_engine_kwargs_use_pool_for_regular_database_url() -> None:
    kwargs = build_engine_kwargs(
        "postgresql+asyncpg://sourcecast:sourcecast_dev@localhost:5432/sourcecast",
        debug=False,
    )

    assert kwargs["pool_size"] == 10
    assert kwargs["max_overflow"] == 20
    assert "connect_args" not in kwargs
    assert "poolclass" not in kwargs


def test_engine_kwargs_disable_prepared_statement_cache_for_neon_pooler() -> None:
    kwargs = build_engine_kwargs(
        "postgresql+asyncpg://user:password@ep-demo-123-pooler.c-2.us-east-1.aws.neon.tech"
        "/sourcecast?ssl=require",
        debug=False,
    )

    assert kwargs["poolclass"] is NullPool
    assert kwargs["connect_args"]["statement_cache_size"] == 0
    assert callable(kwargs["connect_args"]["prepared_statement_name_func"])
    assert kwargs["connect_args"]["prepared_statement_name_func"]().startswith("__sourcecast_")
    assert "pool_size" not in kwargs


def test_engine_kwargs_keep_a_pool_for_neon_direct_connection() -> None:
    kwargs = build_engine_kwargs(
        "postgresql+asyncpg://user:password@ep-demo-123.c-2.us-east-1.aws.neon.tech"
        "/sourcecast?ssl=require",
        debug=False,
    )

    assert kwargs["pool_size"] == 10
    assert "poolclass" not in kwargs
