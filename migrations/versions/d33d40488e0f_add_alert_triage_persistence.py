"""add alert triage persistence

Revision ID: d33d40488e0f
Revises: d9af4388f20a
Create Date: 2026-06-18 18:25:02.565232

设计要点（docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md §4.1）:

- 新增 ``alert_records`` (告警快照事实来源) 和 ``alert_triage_events`` (triage 历史事实来源)。
- ``(user_id, alert_id)`` 唯一约束,避免同一告警重复入库。
- 关键索引:
  - ``ix_alert_records_user_processed`` / ``ix_alert_records_user_status_processed``
    服务 ``GET /alerts`` 按 user + processed_at / status 排序的常见查询。
  - ``ix_alert_records_alert_id`` 服务 history 端点先按 alert_id 定位 record。
  - ``ix_alert_triage_events_user_alert_created`` / ``ix_alert_triage_events_record_created``
    服务 history 端点的 user/record 维度时间排序。
- raw alert / llm analysis 用 ``Text`` 存 JSON 字符串(``json.dumps(..., ensure_ascii=False)``);
  不依赖 PostgreSQL JSONB,以便 SQLite 测试库与 Compose PostgreSQL 走同一份代码。
- ``downgrade`` 必须按依赖反序 drop indexes / tables,确保可回滚。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd33d40488e0f'
down_revision: Union[str, None] = 'd9af4388f20a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alert_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('raw_alert_json', sa.Text(), nullable=False),
        sa.Column('llm_analysis_json', sa.Text(), nullable=True),
        sa.Column('analysis_error', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=False),
        sa.Column('triage_status', sa.String(length=32), nullable=False),
        sa.Column('triage_disposition', sa.String(length=64), nullable=True),
        sa.Column('triage_note', sa.Text(), nullable=True),
        sa.Column('triage_updated_at', sa.DateTime(), nullable=True),
        sa.Column('triage_updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['triage_updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'alert_id', name='uq_alert_records_user_alert'),
    )
    with op.batch_alter_table('alert_records', schema=None) as batch_op:
        batch_op.create_index('ix_alert_records_alert_id', ['alert_id'], unique=False)
        batch_op.create_index(
            'ix_alert_records_user_processed', ['user_id', 'processed_at'], unique=False
        )
        batch_op.create_index(
            'ix_alert_records_user_status_processed',
            ['user_id', 'triage_status', 'processed_at'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_alert_records_id'), ['id'], unique=False
        )

    op.create_table(
        'alert_triage_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_record_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.String(length=64), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('disposition', sa.String(length=64), nullable=True),
        sa.Column('analyst_note', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['alert_record_id'], ['alert_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('alert_triage_events', schema=None) as batch_op:
        batch_op.create_index(
            'ix_alert_triage_events_user_alert_created',
            ['user_id', 'alert_id', 'created_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_alert_triage_events_record_created',
            ['alert_record_id', 'created_at'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_alert_triage_events_id'), ['id'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('alert_triage_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alert_triage_events_id'))
        batch_op.drop_index('ix_alert_triage_events_record_created')
        batch_op.drop_index('ix_alert_triage_events_user_alert_created')

    op.drop_table('alert_triage_events')
    with op.batch_alter_table('alert_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alert_records_id'))
        batch_op.drop_index('ix_alert_records_user_status_processed')
        batch_op.drop_index('ix_alert_records_user_processed')
        batch_op.drop_index('ix_alert_records_alert_id')

    op.drop_table('alert_records')
