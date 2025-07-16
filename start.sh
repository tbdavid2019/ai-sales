#!/bin/bash
# AI Sales 系統啟動腳本

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 顯示選項
show_menu() {
    echo -e "${BLUE}=== AI Sales 系統啟動選項 ===${NC}"
    echo "1. 啟動 API 服務 (port 8000)"
    echo "2. 啟動 Streamlit 介面 (port 8501)"
    echo "3. 啟動 Gradio 介面 (port 7860)"
    echo "4. 同時啟動所有服務"
    echo "5. 使用 Docker Compose 啟動"
    echo "6. 退出"
    echo
}

# 啟動 API
start_api() {
    echo -e "${GREEN}🚀 啟動 API 服務...${NC}"
    python main.py
}

# 啟動 Streamlit
start_streamlit() {
    echo -e "${GREEN}🚀 啟動 Streamlit 介面...${NC}"
    streamlit run app_streamlit.py --server.port=8501 --server.address=0.0.0.0
}

# 啟動 Gradio
start_gradio() {
    echo -e "${GREEN}🚀 啟動 Gradio 介面...${NC}"
    python app_gradio.py
}

# 同時啟動所有服務
start_all() {
    echo -e "${GREEN}🚀 同時啟動所有服務...${NC}"
    
    # 在背景啟動 API
    python main.py &
    API_PID=$!
    
    # 在背景啟動 Streamlit
    streamlit run app_streamlit.py --server.port=8501 --server.address=0.0.0.0 &
    STREAMLIT_PID=$!
    
    # 在背景啟動 Gradio
    python app_gradio.py &
    GRADIO_PID=$!
    
    echo -e "${GREEN}所有服務已啟動：${NC}"
    echo -e "  API: http://localhost:8000"
    echo -e "  Streamlit: http://localhost:8501"
    echo -e "  Gradio: http://localhost:7860"
    echo
    echo -e "${YELLOW}按 Ctrl+C 停止所有服務${NC}"
    
    # 等待中斷信號
    trap 'kill $API_PID $STREAMLIT_PID $GRADIO_PID; exit' INT
    wait
}

# 使用 Docker Compose
start_docker() {
    echo -e "${GREEN}🚀 使用 Docker Compose 啟動...${NC}"
    docker-compose up --build
}

# 主程式
main() {
    while true; do
        show_menu
        read -p "請選擇 (1-6): " choice
        
        case $choice in
            1)
                start_api
                ;;
            2)
                start_streamlit
                ;;
            3)
                start_gradio
                ;;
            4)
                start_all
                ;;
            5)
                start_docker
                ;;
            6)
                echo -e "${GREEN}再見！${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}無效的選擇，請選擇 1-6${NC}"
                ;;
        esac
        
        echo
        read -p "按 Enter 繼續..."
        echo
    done
}

# 檢查是否在虛擬環境中
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}警告：您不在虛擬環境中，建議先啟動虛擬環境${NC}"
    echo -e "執行：${GREEN}source .venv/bin/activate${NC}"
    echo
fi

# 啟動主程式
main
