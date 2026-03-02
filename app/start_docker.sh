#!/usr/bin/env bash

# Docker 启动脚本（从 app 目录执行）
#
# 用法示例：
#   ./start_docker.sh               # 默认：PostgreSQL 模式（启动）
#   ./start_docker.sh pg up         # PostgreSQL 模式启动
#   ./start_docker.sh sqlite up     # SQLite 模式启动
#   ./start_docker.sh sqlite down   # SQLite 模式停服
#   ./start_docker.sh pg logs       # 查看 PostgreSQL 模式日志
#
# 说明：
# - 脚本会自动切到项目根目录执行 docker compose。
# - 若缺少对应环境文件，会自动从 example 模板拷贝一份。

set -euo pipefail

# 获取项目根目录（当前脚本在 app/ 下）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 参数定义
MODE="${1:-pg}"   # sqlite | pg | postgres | postgresql
ACTION="${2:-up}"     # up | down | logs | restart

# 规范化模式参数
case "${MODE}" in
  sqlite)
    COMPOSE_FILE="docker-compose.sqlite.yml"
    ENV_FILE=".env"
    EXAMPLE_FILE="env.sqlite.example"
    ;;
  pg|postgres|postgresql)
    COMPOSE_FILE="docker-compose.postgresql.yml"
    ENV_FILE=".env"
    EXAMPLE_FILE="env.postgresql.example"
    ;;
  *)
    echo "不支持的模式: ${MODE}"
    echo "可用模式: sqlite | pg"
    exit 1
    ;;
esac

cd "${PROJECT_ROOT}"

# 如果环境文件不存在，则自动从模板生成（首次启动更友好）
if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${EXAMPLE_FILE}" ]]; then
    cp "${EXAMPLE_FILE}" "${ENV_FILE}"
    echo "未找到 ${ENV_FILE}，已根据 ${EXAMPLE_FILE} 自动创建。"
    echo "请按需修改其中配置（尤其是 OPENAI_API_KEY、密码等）。"
  else
    echo "缺少环境文件 ${ENV_FILE}，且未找到模板 ${EXAMPLE_FILE}。"
    exit 1
  fi
fi

echo "项目根目录: ${PROJECT_ROOT}"
echo "启动模式: ${MODE}"
echo "Compose 文件: ${COMPOSE_FILE}"
echo "环境文件: ${ENV_FILE}"

case "${ACTION}" in
  up)
    # 启动并后台运行，首次会自动构建镜像
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build
    echo "启动完成。可访问: http://localhost:8000/docs"
    ;;
  down)
    # 停止并移除当前 compose 下的容器与网络
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
    echo "已停止 ${MODE} 模式服务。"
    ;;
  logs)
    # 持续查看日志（Ctrl+C 退出）
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs -f
    ;;
  restart)
    # 快速重启
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build
    echo "重启完成。"
    ;;
  *)
    echo "不支持的动作: ${ACTION}"
    echo "可用动作: up | down | logs | restart"
    exit 1
    ;;
esac
