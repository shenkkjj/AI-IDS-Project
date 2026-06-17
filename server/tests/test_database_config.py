"""``server.core.database`` 数据库 URL 解析与 engine 构造契约测试。

设计目标（docs/agent/M2_01_DATABASE_URL_ALEMBIC_BASELINE_TASK.md §3 目标边界）：

- ``DATABASE_URL`` 未设置时使用 repo 内 ``data/app.db`` SQLite；
- ``DATABASE_URL=sqlite:///...`` 直接使用；
- ``DATABASE_URL=sqlite+aiosqlite:///...`` 应被同步 engine 接受（转同步 driver）
  或在未配置时清晰报错，而不是静默使用别的数据库；
- PostgreSQL URL 不被静默忽略：未装 driver 时必须清晰报错，不掩盖；
- ``connect_args={"check_same_thread": False}`` 只用于 SQLite，不用于 PostgreSQL；
- 测试过程不会污染真实 ``data/app.db``。

实现说明：本文件只测试 helper（``default_database_url`` /
``load_database_url`` / ``normalize_database_url`` / ``build_engine_kwargs`` /
``create_app_engine``）和模块级 ``engine`` 行为。
"""
from __future__ import annotations

import importlib
import os
import sqlite3
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_database() -> None:
    """强制 ``server.core.database`` 重新执行模块级初始化。

    调用方应自行用 ``monkeypatch.setenv`` / ``delenv`` 控制 ``DATABASE_URL``；
    本 helper 只 reload，不再触碰 env，避免与 monkeypatch 的恢复逻辑冲突。
    """
    import server.core.database as db_module
    importlib.reload(db_module)


# ---------------------------------------------------------------------------
# default_database_url / load_database_url
# ---------------------------------------------------------------------------


def test_default_database_url_points_to_repo_data_dir(project_root) -> None:
    """未设置 DATABASE_URL 时，``default_database_url`` 必须指向 repo 内 data/app.db。"""
    from server.core.database import default_database_url

    expected = (project_root / "data" / "app.db").as_posix()
    assert default_database_url() == f"sqlite:///{expected}"


def test_load_database_url_returns_default_when_unset(
    monkeypatch: pytest.MonkeyPatch, project_root
) -> None:
    """``load_database_url`` 在 DATABASE_URL 未设置时回退到 default。"""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from server.core.database import load_database_url

    expected = f"sqlite:///{(project_root / 'data' / 'app.db').as_posix()}"
    assert load_database_url() == expected


def test_load_database_url_returns_env_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """``load_database_url`` 在 DATABASE_URL 已设置时原样返回。"""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/custom.db")
    from server.core.database import load_database_url

    assert load_database_url() == "sqlite:///tmp/custom.db"


# ---------------------------------------------------------------------------
# normalize_database_url
# ---------------------------------------------------------------------------


def test_normalize_database_url_strips_aiosqlite_for_sync_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """``sqlite+aiosqlite:///...`` 同步 engine 不支持，必须能转换为 ``sqlite:///...``。"""
    target = tmp_path / "x.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{target.as_posix()}")
    from server.core.database import normalize_database_url

    assert normalize_database_url(f"sqlite+aiosqlite:///{target.as_posix()}") == (
        f"sqlite:///{target.as_posix()}"
    )


def test_normalize_database_url_keeps_plain_sqlite_unchanged(tmp_path) -> None:
    """``sqlite:///...`` 已经是同步 driver，应该原样返回。"""
    from server.core.database import normalize_database_url

    url = f"sqlite:///{(tmp_path / 'plain.db').as_posix()}"
    assert normalize_database_url(url) == url


def test_normalize_database_url_passes_through_postgres(tmp_path) -> None:
    """PostgreSQL URL 不应在 normalize 阶段被改写，driver 验证留到 build 阶段。"""
    from server.core.database import normalize_database_url

    url = "postgresql+psycopg://user:pass@db:5432/cybersentinel"
    assert normalize_database_url(url) == url


# ---------------------------------------------------------------------------
# build_engine_kwargs
# ---------------------------------------------------------------------------


def test_build_engine_kwargs_applies_check_same_thread_for_sqlite(tmp_path) -> None:
    """SQLite URL 必须带 ``check_same_thread=False``。"""
    from server.core.database import build_engine_kwargs

    url = f"sqlite:///{(tmp_path / 'x.db').as_posix()}"
    kwargs = build_engine_kwargs(url)
    assert kwargs.get("connect_args") == {"check_same_thread": False}


def test_build_engine_kwargs_does_not_apply_check_same_thread_for_postgres() -> None:
    """PostgreSQL URL 不应带 ``check_same_thread``，那是 SQLite 专属参数。"""
    from server.core.database import build_engine_kwargs

    url = "postgresql+psycopg://user:pass@db:5432/cybersentinel"
    kwargs = build_engine_kwargs(url)
    assert "check_same_thread" not in kwargs.get("connect_args", {})


# ---------------------------------------------------------------------------
# create_app_engine
# ---------------------------------------------------------------------------


def test_create_app_engine_writes_table_to_temp_sqlite(tmp_path) -> None:
    """``create_app_engine`` 能在临时 SQLite 路径上创建表，不污染 repo data。"""
    from sqlalchemy import Column, Integer, MetaData, Table

    from server.core.database import create_app_engine

    url = f"sqlite:///{(tmp_path / 'tmp.db').as_posix()}"
    engine = create_app_engine(url)
    meta = MetaData()
    Table(
        "probe",
        meta,
        Column("id", Integer, primary_key=True),
    )
    meta.create_all(engine)

    with engine.connect() as conn:
        rows = list(
            conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='probe'"
            )
        )
    assert rows, "probe 表必须在临时 SQLite 库中建好"
    engine.dispose()


def test_create_app_engine_rejects_postgres_without_driver(monkeypatch) -> None:
    """PostgreSQL URL 在未安装 driver 时必须抛清晰错误，而不是被静默降级。"""
    from server.core.database import create_app_engine

    # 这条 URL 使用一个明显没装的 driver，避免本地依赖影响。
    url = "postgresql+nonexistent_driver://user:pass@db:5432/cybersentinel"
    with pytest.raises(Exception) as exc_info:
        create_app_engine(url)
    msg = str(exc_info.value).lower()
    # 不应包含 "not implemented" / "fallback" 这类掩盖语
    assert "fallback" not in msg
    assert "sqlite" not in msg or (
        "could not" in msg or "no module" in msg or "module" in msg
    )


# ---------------------------------------------------------------------------
# 模块级 engine 行为
# ---------------------------------------------------------------------------


def test_module_engine_uses_env_database_url(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """reload database 模块后，模块级 ``engine`` 应当反映 ``DATABASE_URL``。"""
    target = tmp_path / "module.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target.as_posix()}")
    _reload_database()
    import server.core.database as db_module

    assert str(db_module.engine.url) == f"sqlite:///{target.as_posix()}"


def test_module_engine_does_not_touch_real_app_db(
    monkeypatch: pytest.MonkeyPatch, project_root
) -> None:
    """未设置 DATABASE_URL 时，模块级 ``engine`` 仍指向默认 ``data/app.db``，
    但本测试不会触发 ``create_all`` 或写入行为，因此真实 db 不应被新增对象。"""
    real_db = project_root / "data" / "app.db"
    existed_before = real_db.exists()
    size_before = real_db.stat().st_size if existed_before else 0
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _reload_database()
    import server.core.database as db_module

    # 应当指向默认 path
    expected = f"sqlite:///{real_db.as_posix()}"
    assert str(db_module.engine.url) == expected
    # 不应触发任何 init 副作用
    if existed_before:
        assert real_db.stat().st_size == size_before


# ---------------------------------------------------------------------------
# SQL 路由基础 — 测试 helper 行为可独立重复使用
# ---------------------------------------------------------------------------


def test_normalize_database_url_handles_relative_path(tmp_path) -> None:
    """相对路径不应被改写成绝对路径，保持 ``normalize`` 的最小职责。"""
    from server.core.database import normalize_database_url

    assert normalize_database_url("sqlite:///./data/app.db") == "sqlite:///./data/app.db"
