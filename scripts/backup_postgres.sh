#!/bin/bash
# PostgreSQL 自动备份脚本
# 用于 docker-compose 环境中的定期备份

set -e

# 配置
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=7

# 确保备份目录存在
mkdir -p ${BACKUP_DIR}

# 从环境变量读取数据库配置
DB_HOST=${POSTGRES_HOST:-postgres}
DB_PORT=${POSTGRES_PORT:-5432}
DB_NAME=${POSTGRES_DB:-lingjing}
DB_USER=${POSTGRES_USER:-postgres}

echo "[$(date)] 开始备份数据库 ${DB_NAME}..."

# 执行备份并压缩
PGPASSWORD=${POSTGRES_PASSWORD} pg_dump \
    -h ${DB_HOST} \
    -p ${DB_PORT} \
    -U ${DB_USER} \
    -d ${DB_NAME} \
    --format=custom \
    --blobs \
    --verbose \
    | gzip > ${BACKUP_FILE}

if [ $? -eq 0 ]; then
    echo "[$(date)] 备份成功: ${BACKUP_FILE}"
    echo "[$(date)] 备份大小: $(du -h ${BACKUP_FILE} | cut -f1)"
else
    echo "[$(date)] 备份失败!" >&2
    exit 1
fi

# 清理旧备份
echo "[$(date)] 清理 ${RETENTION_DAYS} 天前的备份文件..."
find ${BACKUP_DIR} -name "backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete

# 列出当前所有备份
echo "[$(date)] 当前备份列表:"
ls -lh ${BACKUP_DIR}/backup_*.sql.gz 2>/dev/null || echo "无备份文件"

echo "[$(date)] 备份任务完成"
