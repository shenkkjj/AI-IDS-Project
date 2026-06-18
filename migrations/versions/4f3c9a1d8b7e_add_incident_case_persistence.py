"""add incident case persistence

Revision ID: 4f3c9a1d8b7e
Revises: d33d40488e0f
Create Date: 2026-06-18 19:30:00.000000

设计要点（docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md §4）:

- 新增 ``incidents`` (案件事实来源), ``incident_alert_links`` (告警关联事实来源)
  和 ``incident_events`` (事件时间线事实来源) 三张表。
- ``(user_id, incident_id)`` 唯一约束,避免同一案件重复入库。
- 关键索引:
  - ``ix_incidents_user_updated`` / ``ix_incidents_user_status_updated``
    服务 ``GET /incidents`` 的常规分页与按状态过滤。
  - ``ix_incidents_created_from_alert`` 服务从首条告警反查 incident。
  - ``ix_incident_alert_links_incident_active`` 服务 incident 详情中
    active link 的快速查询(配合 ``removed_at IS NULL``)。
  - ``ix_incident_alert_links_user_alert`` 服务按 user 维度查 alert 关联。
  - ``ix_incident_alert_links_alert_record`` 服务按 alert_record_id 反查。
  - ``ix_incident_events_incident_created`` / ``ix_incident_events_user_created``
    服务事件时间线的 user/record 维度时间排序。
- ``detail`` / ``note`` 用 ``Text``;不依赖 PostgreSQL JSONB,以便 SQLite 测试
  库与 Compose PostgreSQL 走同一份代码。
- ``downgrade`` 按依赖反序 drop indexes / tables,确保可回滚。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f3c9a1d8b7e'
down_revision: Union[str, None] = 'd33d40488e0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'incidents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('assignee_user_id', sa.Integer(), nullable=True),
        sa.Column('created_from_alert_id', sa.String(length=64), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assignee_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'incident_id', name='uq_incidents_user_incident'),
    )
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.create_index('ix_incidents_created_from_alert', ['created_from_alert_id'], unique=False)
        batch_op.create_index(
            'ix_incidents_user_status_updated',
            ['user_id', 'status', 'updated_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_incidents_user_updated', ['user_id', 'updated_at'], unique=False
        )
        batch_op.create_index(batch_op.f('ix_incidents_id'), ['id'], unique=False)

    op.create_table(
        'incident_alert_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incident_record_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('alert_record_id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.String(length=64), nullable=False),
        sa.Column('linked_by', sa.Integer(), nullable=True),
        sa.Column('linked_at', sa.DateTime(), nullable=False),
        sa.Column('removed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['alert_record_id'], ['alert_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['incident_record_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('incident_alert_links', schema=None) as batch_op:
        batch_op.create_index(
            'ix_incident_alert_links_alert_record',
            ['alert_record_id'],
            unique=False,
        )
        batch_op.create_index(
            'ix_incident_alert_links_incident_active',
            ['incident_record_id', 'removed_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_incident_alert_links_user_alert',
            ['user_id', 'alert_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_incident_alert_links_id'), ['id'], unique=False
        )

    op.create_table(
        'incident_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incident_record_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=True),
        sa.Column('detail', sa.Text(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_record_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('incident_events', schema=None) as batch_op:
        batch_op.create_index(
            'ix_incident_events_incident_created',
            ['incident_record_id', 'created_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_incident_events_user_created',
            ['user_id', 'created_at'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_incident_events_id'), ['id'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('incident_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incident_events_id'))
        batch_op.drop_index('ix_incident_events_user_created')
        batch_op.drop_index('ix_incident_events_incident_created')

    op.drop_table('incident_events')

    with op.batch_alter_table('incident_alert_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incident_alert_links_id'))
        batch_op.drop_index('ix_incident_alert_links_user_alert')
        batch_op.drop_index('ix_incident_alert_links_incident_active')
        batch_op.drop_index('ix_incident_alert_links_alert_record')

    op.drop_table('incident_alert_links')

    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incidents_id'))
        batch_op.drop_index('ix_incidents_user_updated')
        batch_op.drop_index('ix_incidents_user_status_updated')
        batch_op.drop_index('ix_incidents_created_from_alert')

    op.drop_table('incidents')
