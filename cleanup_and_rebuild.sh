#!/bin/bash

# AI Sales 系統清理和重新構建腳本
# 此腳本會清理舊的容器和資料，並重新構建沒有 PostgreSQL 的環境

set -e

echo "🧹 開始清理和重新構建 AI Sales 系統..."

# 停止所有容器
echo "📦 停止所有容器..."
docker-compose down -v

# 移除舊的映像
echo "🗑️ 移除舊的映像..."
docker-compose down --rmi all --volumes --remove-orphans

# 清理 Docker 系統
echo "🧹 清理 Docker 系統..."
docker system prune -f

# 重新構建映像
echo "🏗️ 重新構建映像..."
docker-compose build --no-cache

# 重新啟動服務
echo "🚀 啟動服務..."
docker-compose up -d

# 等待服務啟動
echo "⏳ 等待服務啟動..."
sleep 10

# 檢查服務狀態
echo "🔍 檢查服務狀態..."
docker-compose ps

# 檢查 Redis 連接
echo "🔍 檢查 Redis 連接..."
docker-compose exec redis redis-cli ping

# 檢查 ChromaDB 連接
echo "🔍 檢查 ChromaDB 連接..."
curl -s http://localhost:8001/api/v1/heartbeat || echo "ChromaDB 連接失敗"

# 檢查 API 健康狀態
echo "🔍 檢查 API 健康狀態..."
sleep 5
curl -s http://localhost:8000/health || echo "API 健康檢查失敗"

echo "✅ 清理和重新構建完成！"
echo ""
echo "📊 系統資訊:"
echo "  - API 服務: http://localhost:8000"
echo "  - ChromaDB: http://localhost:8001"
echo "  - Redis: localhost:6379"
echo ""
echo "🧪 測試命令:"
echo "  - 健康檢查: curl http://localhost:8000/health"
echo "  - 測試對話: curl -X POST http://localhost:8000/v1/chat/completions ..."
echo ""
echo "📋 管理命令:"
echo "  - 查看日誌: docker-compose logs -f aisales-api"
echo "  - 停止服務: docker-compose down"
echo "  - 重新啟動: docker-compose up -d"
