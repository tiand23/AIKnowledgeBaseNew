# =============================================
# Kafka 3.9.0 KRaft 模式启动脚本 (Windows)
# =============================================

$ErrorActionPreference = "Stop"
$LOG_DIR = "C:\tmp\kraft-combined-logs"
$CONFIG_FILE = ".\config\kraft\server.properties"

Write-Host "=== Kafka KRaft Mode Startup Script (Windows) ==="
Write-Host "时间: $(Get-Date)"
Write-Host "目录: $(Get-Location)"
Write-Host ""

# 检查配置文件
if (-not (Test-Path $CONFIG_FILE)) {
    Write-Host "✗ 配置文件不存在: $CONFIG_FILE"
    exit 1
}

# 检查 kafka-storage.bat
if (-not (Test-Path ".\bin\windows\kafka-storage.bat")) {
    Write-Host "✗ kafka-storage.bat 不存在，请在 Kafka 目录下运行"
    exit 1
}

# 清理旧日志目录（如果存在）
if (Test-Path $LOG_DIR) {
    Write-Host "检测到旧日志目录，正在清理..."
    Remove-Item -Recurse -Force $LOG_DIR
    Write-Host "✓ 已清理 $LOG_DIR"
}

# 生成 Cluster ID
Write-Host "`n=== 生成集群 ID ==="
$KAFKA_CLUSTER_ID = & .\bin\windows\kafka-storage.bat random-uuid
Write-Host "生成的 Cluster ID: $KAFKA_CLUSTER_ID"

# 格式化存储
Write-Host "`n=== 格式化存储目录 ==="
& .\bin\windows\kafka-storage.bat format -t $KAFKA_CLUSTER_ID -c $CONFIG_FILE
Write-Host "✓ 格式化完成"

# 启动 Kafka
Write-Host "`n=== 启动 Kafka 服务器 ==="
Write-Host "提示: 使用 Ctrl + C 停止服务器"
& .\bin\windows\kafka-server-start.bat $CONFIG_FILE
