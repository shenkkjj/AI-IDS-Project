-- SC-22: audit 表新增复合索引
-- 用于支持 get_stats 聚合查询与"用户归因 + 时间窗口"查询
-- 应用方式: psql "$DATABASE_URL" -f server/migrations/sql/sc22_audit_indexes.sql

CREATE INDEX IF NOT EXISTS ix_audit_logs_action_status_created
  ON audit_logs (action, status, created_at);

CREATE INDEX IF NOT EXISTS ix_audit_logs_user_action_created
  ON audit_logs (user_id, action, created_at);
