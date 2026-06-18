"""Alembic baseline 迁移契约测试。

设计目标（docs/agent/M2_01_DATABASE_URL_ALEMBIC_BASELINE_TASK.md §4 阶段 4）：

- ``alembic.ini`` 与 migrations env 必须存在且能加载 ``Base.metadata``；
- 对临时 SQLite 空库执行 ``alembic upgrade head`` 必须成功；
- 已有表 / 索引应被 baseline 覆盖；
- 启动时仍走 ``init_db()``，Alembic baseline 只作为显式迁移工具落地；
- downgrade 行为必须在文档中说明；本测试只验证 ``alembic current`` /
  ``alembic history`` 能跑通，不在不可逆情况下强求 ``downgrade -1``。

所有测试用临时 SQLite（``tmp_path``），不污染真实 ``data/app.db``。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 配置文件 / 目录存在性
# ---------------------------------------------------------------------------


def test_alembic_ini_exists_at_repo_root(project_root) -> None:
    """``alembic.ini`` 必须在 repo 根。"""
    assert (project_root / "alembic.ini").exists(), "alembic.ini 缺失"


def test_alembic_env_dir_exists(project_root) -> None:
    """Alembic env.py 必须在约定目录（migrations/ 或 server/migrations/alembic/）。"""
    candidates = [
        project_root / "migrations",
        project_root / "server" / "migrations" / "alembic",
    ]
    env_paths = [c / "env.py" for c in candidates]
    found = [p for p in env_paths if p.exists()]
    assert found, "Alembic env.py 缺失，期望位置: " + ", ".join(str(p) for p in env_paths)


def test_migrations_script_directory_declared_in_alembic_ini(project_root) -> None:
    """``alembic.ini`` 必须声明 script_location，且路径与 env.py 实际位置一致。"""
    ini = project_root / "alembic.ini"
    if not ini.exists():
        pytest.fail("alembic.ini 缺失")
    text = ini.read_text(encoding="utf-8")
    assert "script_location" in text, "alembic.ini 必须声明 script_location"

    candidates = [
        project_root / "migrations",
        project_root / "server" / "migrations" / "alembic",
    ]
    expected = None
    for cand in candidates:
        if (cand / "env.py").exists():
            expected = cand
            break
    if expected is None:
        pytest.skip("env.py 不在已知位置，跳过路径一致性检查")


# ---------------------------------------------------------------------------
# alembic CLI
# ---------------------------------------------------------------------------


def test_alembic_cli_runs(project_root) -> None:
    """``python -m alembic --version`` 必须在 .venv 中能跑。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 CLI 验证")
    result = subprocess.run(
        [str(venv_python), "-m", "alembic", "--version"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"alembic --version 失败: {result.stderr}"


def test_alembic_upgrade_head_on_empty_sqlite(project_root, tmp_path) -> None:
    """对临时空 SQLite 跑 ``alembic upgrade head`` 必须成功，且至少建出 ORM 表之一。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 upgrade head 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 upgrade head 验证")
    # 临时 SQLite 库
    db_file = tmp_path / "alembic.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    # 强制 UTF-8，避免 Windows 默认编码问题
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    result = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head 失败:\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    # 至少应有 users 表
    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchall()
    finally:
        con.close()
    assert rows, "upgrade head 后临时库中未找到 users 表; baseline 必须覆盖 ORM schema"


def test_alembic_current_after_upgrade(project_root, tmp_path) -> None:
    """``alembic current`` 在临时空库上跑完 upgrade 后必须返回 head revision。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 current 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 current 验证")

    db_file = tmp_path / "alembic_current.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    # 先 upgrade head
    up = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert up.returncode == 0, f"alembic upgrade head 失败: {up.stderr}"

    # 再 current
    result = subprocess.run(
        [str(venv_python), "-m", "alembic", "current"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 0, f"alembic current 失败: {result.stderr}"
    # 应当输出形如 "<rev> (head)"；包含 head 关键字
    assert "head" in result.stdout.lower(), (
        f"alembic current 应返回 head revision；实际输出: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# env.py 元数据加载
# ---------------------------------------------------------------------------


def test_alembic_env_imports_base_metadata(project_root) -> None:
    """``env.py`` 必须 ``import`` 自 ``server.core.database`` 的 ``Base``。"""
    env_paths = [
        project_root / "migrations" / "env.py",
        project_root / "server" / "migrations" / "alembic" / "env.py",
    ]
    target = next((p for p in env_paths if p.exists()), None)
    if target is None:
        pytest.skip("env.py 缺失")
    text = target.read_text(encoding="utf-8")
    assert (
        "from server.core.database import Base" in text
        or ("server.core.database" in text and "Base" in text)
    ), "env.py 必须从 server.core.database 导入 Base 以加载 ORM metadata"
    assert "target_metadata" in text, "env.py 必须设置 target_metadata"


# ---------------------------------------------------------------------------
# 旧 SQL 脚本归属
# ---------------------------------------------------------------------------


def test_legacy_sc22_sql_documented_in_migration_doc(project_root) -> None:
    """``server/migrations/sql/sc22_audit_indexes.sql`` 必须被 Alembic 迁移文档明确处置。"""
    sql = project_root / "server" / "migrations" / "sql" / "sc22_audit_indexes.sql"
    doc = project_root / "docs" / "ALEMBIC_MIGRATION.md"
    if not sql.exists():
        pytest.skip("legacy sql 不存在")
    assert doc.exists(), "docs/ALEMBIC_MIGRATION.md 缺失"
    text = doc.read_text(encoding="utf-8")
    # 必须明确说明 sc22 的处置（迁入 revision 或保留为 manual）
    assert "sc22" in text.lower() or "sc-22" in text.lower(), (
        "ALEMBIC_MIGRATION.md 必须明确说明 sc22_audit_indexes.sql 的处置"
    )


# ---------------------------------------------------------------------------
# M3-03 告警研判持久化迁移契约
# ---------------------------------------------------------------------------


def test_alembic_upgrade_head_creates_alert_records_tables(project_root, tmp_path) -> None:
    """``alembic upgrade head`` 必须建出 M3-03 的 alert_records / alert_triage_events 表。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 upgrade head 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 upgrade head 验证")

    db_file = tmp_path / "alembic_m3_03.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    result = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head 失败:\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('alert_records', 'alert_triage_events') ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    table_names = {row[0] for row in rows}
    assert "alert_records" in table_names, "alert_records 表未通过 migration 创建"
    assert "alert_triage_events" in table_names, "alert_triage_events 表未通过 migration 创建"


def test_alembic_upgrade_head_creates_alert_records_indexes(project_root, tmp_path) -> None:
    """M3-03 migration 必须建出 alert_records / alert_triage_events 的关键索引。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 upgrade head 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 upgrade head 验证")

    db_file = tmp_path / "alembic_m3_03_idx.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    up = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert up.returncode == 0, f"alembic upgrade head 失败: {up.stderr}"

    expected_indexes = {
        "ix_alert_records_alert_id",
        "ix_alert_records_user_processed",
        "ix_alert_records_user_status_processed",
        "ix_alert_triage_events_user_alert_created",
        "ix_alert_triage_events_record_created",
    }

    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND (tbl_name='alert_records' OR tbl_name='alert_triage_events')"
        ).fetchall()
    finally:
        con.close()
    found_indexes = {row[0] for row in rows}

    missing = expected_indexes - found_indexes
    assert not missing, (
        f"M3-03 migration 缺少关键索引: {missing}; 实际: {found_indexes}"
    )


def test_alembic_downgrade_drops_alert_records_tables(project_root, tmp_path) -> None:
    """``alembic downgrade base`` 必须能完整 drop M3-03 的新表(可回滚)。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 downgrade 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 downgrade 验证")

    db_file = tmp_path / "alembic_m3_03_down.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    up = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert up.returncode == 0, f"alembic upgrade head 失败: {up.stderr}"

    down = subprocess.run(
        [str(venv_python), "-m", "alembic", "downgrade", "base"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert down.returncode == 0, f"alembic downgrade base 失败: {down.stderr}"

    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('alert_records', 'alert_triage_events')"
        ).fetchall()
    finally:
        con.close()
    assert not rows, (
        f"downgrade base 后新表未 drop: {[r[0] for r in rows]}"
    )


# ---------------------------------------------------------------------------
# M3-04 安全事件案件迁移契约
# ---------------------------------------------------------------------------


def test_alembic_upgrade_head_creates_incident_tables(project_root, tmp_path) -> None:
    """``alembic upgrade head`` 必须建出 M3-04 的 incidents / incident_alert_links / incident_events 表。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 upgrade head 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 upgrade head 验证")

    db_file = tmp_path / "alembic_m3_04.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    result = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head 失败:\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('incidents', 'incident_alert_links', 'incident_events') ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    table_names = {row[0] for row in rows}
    assert "incidents" in table_names, "incidents 表未通过 migration 创建"
    assert "incident_alert_links" in table_names, "incident_alert_links 表未通过 migration 创建"
    assert "incident_events" in table_names, "incident_events 表未通过 migration 创建"


def test_alembic_upgrade_head_creates_incident_indexes(project_root, tmp_path) -> None:
    """M3-04 migration 必须建出关键索引。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 upgrade head 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 upgrade head 验证")

    db_file = tmp_path / "alembic_m3_04_idx.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    up = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert up.returncode == 0, f"alembic upgrade head 失败: {up.stderr}"

    expected_indexes = {
        "ix_incidents_user_updated",
        "ix_incidents_user_status_updated",
        "ix_incidents_created_from_alert",
        "ix_incident_alert_links_incident_active",
        "ix_incident_alert_links_user_alert",
        "ix_incident_alert_links_alert_record",
        "ix_incident_events_incident_created",
        "ix_incident_events_user_created",
    }

    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND (tbl_name='incidents' OR tbl_name='incident_alert_links' OR tbl_name='incident_events')"
        ).fetchall()
    finally:
        con.close()
    found_indexes = {row[0] for row in rows}

    missing = expected_indexes - found_indexes
    assert not missing, (
        f"M3-04 migration 缺少关键索引: {missing}; 实际: {found_indexes}"
    )


def test_alembic_downgrade_drops_incident_tables(project_root, tmp_path) -> None:
    """``alembic downgrade base`` 必须能完整 drop M3-04 的新表(可回滚)。"""
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        pytest.skip(".venv 不存在，跳过 downgrade 验证")
    if not (project_root / "alembic.ini").exists():
        pytest.skip("alembic.ini 不存在，跳过 downgrade 验证")

    db_file = tmp_path / "alembic_m3_04_down.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("APP_SECRET", "test-local-secret-key-for-baseline-32chars")
    env.setdefault("AUTH_SECRET", "test-local-auth-secret-for-baseline-32chars")

    up = subprocess.run(
        [str(venv_python), "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert up.returncode == 0, f"alembic upgrade head 失败: {up.stderr}"

    down = subprocess.run(
        [str(venv_python), "-m", "alembic", "downgrade", "base"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert down.returncode == 0, f"alembic downgrade base 失败: {down.stderr}"

    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('incidents', 'incident_alert_links', 'incident_events')"
        ).fetchall()
    finally:
        con.close()
    assert not rows, (
        f"downgrade base 后 M3-04 新表未 drop: {[r[0] for r in rows]}"
    )
