#!/bin/bash

# Docker 部署腳本 - 支援 Google Calendar API
# 自動處理 Google Calendar API 憑證設定

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印彩色訊息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查 Google Calendar 憑證
check_google_calendar_setup() {
    print_info "檢查 Google Calendar 憑證..."
    
    # 建立憑證目錄
    mkdir -p credentials
    
    # 檢查 credentials.json
    if [ -f "credentials.json" ]; then
        print_info "發現 credentials.json，移動到憑證目錄"
        mv credentials.json credentials/
    fi
    
    if [ -f "credentials/credentials.json" ]; then
        print_success "Google Calendar 憑證檔案存在"
        chmod 600 credentials/credentials.json
        
        # 檢查是否需要授權
        if [ ! -f "credentials/token.json" ]; then
            print_warning "首次設定需要進行 Google Calendar 授權"
            echo "請按任意鍵繼續進行授權流程..."
            read -n 1 -s
            
            print_info "開始授權流程..."
            python3 -c "
import asyncio
import sys
import os
sys.path.append('.')

try:
    from app.integrations.google_calendar import google_calendar
    
    async def setup():
        print('正在初始化 Google Calendar API...')
        success = await google_calendar.initialize()
        if success:
            print('✅ Google Calendar API 授權成功')
        else:
            print('❌ Google Calendar API 授權失敗')
            return False
        return True
    
    result = asyncio.run(setup())
    if not result:
        sys.exit(1)
        
except ImportError as e:
    print(f'❌ 導入模組失敗: {e}')
    print('請確保已安裝必要的依賴：pip install -r requirements.txt')
    sys.exit(1)
except Exception as e:
    print(f'❌ 授權失敗: {e}')
    sys.exit(1)
"
            
            if [ $? -eq 0 ]; then
                print_success "Google Calendar 授權完成"
                chmod 600 credentials/token.json
                return 0
            else
                print_error "Google Calendar 授權失敗"
                print_warning "系統將使用 Mock 模式運行"
                return 1
            fi
        else
            print_success "Google Calendar token 已存在"
            return 0
        fi
    else
        print_warning "未找到 Google Calendar 憑證檔案"
        print_info "系統將使用 Mock 模式運行"
        print_info "如需使用真實 Google Calendar，請參考 GOOGLE_CALENDAR_SETUP.md"
        return 1
    fi
}
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查必要的工具
check_dependencies() {
    print_info "檢查部署依賴..."
    
    # 檢查 Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安裝，請先安裝 Docker"
        exit 1
    fi
    
    # 檢查 Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安裝，請先安裝 Docker Compose"
        exit 1
    fi
    
    # 檢查 Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 未安裝，請先安裝 Python 3"
        exit 1
    fi
    
    print_success "所有依賴檢查通過"
}

# 設置環境變數
setup_environment() {
    print_info "設置環境變數..."
    
    # 檢查 .env 檔案
    if [ ! -f ".env" ]; then
        print_warning ".env 檔案不存在，創建預設配置..."
        cat > .env << EOF
# API 設定
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false
API_LOG_LEVEL=INFO

# OpenAI 設定
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# Google AI 設定
GOOGLE_API_KEY=your-google-api-key-here

# 資料庫設定
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ChromaDB 設定
CHROMA_HOST=localhost
CHROMA_PORT=8001

# 安全設定
API_KEYS=sk-aisales-prod-key-001,sk-aisales-prod-key-002
JWT_SECRET=your-jwt-secret-here

# 外部服務設定
GOOGLE_CALENDAR_CREDENTIALS_PATH=./credentials/google_calendar.json
CARD_OCR_API_KEY=your-ocr-api-key-here

# 效能設定
MAX_WORKERS=4
MAX_REQUESTS_PER_MINUTE=100
TIMEOUT_SECONDS=30
EOF
        print_warning "請編輯 .env 檔案並設置正確的 API 金鑰"
    fi
    
    # 載入環境變數
    source .env
    
    print_success "環境變數設置完成"
}

# 安裝 Python 依賴
install_python_dependencies() {
    print_info "安裝 Python 依賴..."
    
    # 檢查並創建虛擬環境
    if [ ! -d "venv" ]; then
        print_info "創建虛擬環境..."
        python3 -m venv venv
    fi
    
    # 啟用虛擬環境
    source venv/bin/activate
    
    # 升級 pip
    python -m pip install --upgrade pip
    
    # 安裝依賴
    pip install -r requirements.txt
    
    print_success "Python 依賴安裝完成"
}

# 初始化資料庫
initialize_database() {
    print_info "初始化資料庫..."
    
    # 啟動 Redis 和 ChromaDB
    docker-compose up -d redis chromadb
    
    # 等待服務啟動
    sleep 5
    
    # 初始化知識庫
    source venv/bin/activate
    python init_knowledge_base.py
    
    print_success "資料庫初始化完成"
}

# 運行測試
run_tests() {
    print_info "運行測試..."
    
    source venv/bin/activate
    
    # 運行基本測試
    python test_agents.py
    
    # 運行綜合測試
    python test_comprehensive.py
    
    print_success "測試完成"
}

# 構建 Docker 映像
build_docker_image() {
    print_info "構建 Docker 映像..."
    
    # 構建應用程式映像
    docker build -t aisales-api:latest .
    
    # 標記映像
    docker tag aisales-api:latest aisales-api:$(date +%Y%m%d-%H%M%S)
    
    print_success "Docker 映像構建完成"
}

# 部署服務
deploy_services() {
    print_info "部署服務..."
    
    # 停止現有服務
    docker-compose down
    
    # 啟動所有服務
    docker-compose up -d
    
    # 等待服務啟動
    sleep 10
    
    # 檢查服務狀態
    docker-compose ps
    
    print_success "服務部署完成"
}

# 健康檢查
health_check() {
    print_info "執行健康檢查..."
    
    # 檢查 API 是否可用
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        print_success "API 服務正常"
    else
        print_error "API 服務異常"
        return 1
    fi
    
    # 檢查 Redis 連接
    if docker-compose exec redis redis-cli ping | grep -q "PONG"; then
        print_success "Redis 服務正常"
    else
        print_error "Redis 服務異常"
        return 1
    fi
    
    # 檢查 ChromaDB 連接
    if curl -s http://localhost:8001/api/v1/heartbeat | grep -q "OK"; then
        print_success "ChromaDB 服務正常"
    else
        print_error "ChromaDB 服務異常"
        return 1
    fi
    
    print_success "所有服務健康檢查通過"
}

# 顯示部署資訊
show_deployment_info() {
    print_info "部署資訊："
    echo ""
    echo "🌐 API 端點："
    echo "  - 主要 API: http://localhost:8000"
    echo "  - API 文檔: http://localhost:8000/docs"
    echo "  - 健康檢查: http://localhost:8000/health"
    echo ""
    echo "📊 監控端點："
    echo "  - ChromaDB: http://localhost:8001"
    echo "  - Redis: localhost:6379"
    echo ""
    echo "🔧 管理命令："
    echo "  - 查看日誌: docker-compose logs -f api"
    echo "  - 重啟服務: docker-compose restart api"
    echo "  - 停止服務: docker-compose down"
    echo ""
    echo "📝 測試命令："
    echo "  - 基本測試: python test_agents.py"
    echo "  - 綜合測試: python test_comprehensive.py"
    echo "  - API 測試: curl -X POST http://localhost:8000/v1/chat/completions"
    echo ""
}

# 主函數
main() {
    print_info "🚀 開始部署 AI Sales 系統..."
    
    case "$1" in
        "dev")
            print_info "開發環境部署..."
            check_dependencies
            setup_environment
            check_google_calendar_setup
            install_python_dependencies
            initialize_database
            run_tests
            print_success "開發環境部署完成"
            ;;
        "prod")
            print_info "生產環境部署..."
            check_dependencies
            setup_environment
            check_google_calendar_setup
            install_python_dependencies
            initialize_database
            run_tests
            build_docker_image
            deploy_services
            sleep 5
            health_check
            show_deployment_info
            print_success "生產環境部署完成"
            ;;
        "docker")
            print_info "Docker 部署..."
            check_dependencies
            setup_environment
            check_google_calendar_setup
            build_docker_image
            deploy_services
            sleep 10
            health_check
            show_deployment_info
            print_success "Docker 部署完成"
            ;;
        "test")
            print_info "僅運行測試..."
            check_dependencies
            setup_environment
            install_python_dependencies
            run_tests
            ;;
        "health")
            print_info "執行健康檢查..."
            health_check
            ;;
        "stop")
            print_info "停止所有服務..."
            docker-compose down
            print_success "服務已停止"
            ;;
        "restart")
            print_info "重啟所有服務..."
            docker-compose restart
            sleep 5
            health_check
            print_success "服務已重啟"
            ;;
        "logs")
            print_info "顯示服務日誌..."
            docker-compose logs -f api
            ;;
        *)
            echo "用法: $0 {dev|prod|test|health|stop|restart|logs}"
            echo ""
            echo "  dev     - 開發環境部署"
            echo "  prod    - 生產環境部署"
            echo "  test    - 僅運行測試"
            echo "  health  - 健康檢查"
            echo "  stop    - 停止服務"
            echo "  restart - 重啟服務"
            echo "  logs    - 顯示日誌"
            exit 1
            ;;
    esac
}

# 執行主函數
main "$@"
