// 全域變數來管理攝影機和 WebSocket 狀態
let videoStream = null;
let websocket = null;
let frameInterval = null;

// 啟動視覺分析功能
function startVision(sessionId, videoContainerId, statusElementId) {
    console.log("Attempting to start vision for session:", sessionId);
    const videoContainer = document.getElementById(videoContainerId);
    const statusElement = document.getElementById(statusElementId);

    if (!videoContainer) {
        console.error("Video container not found:", videoContainerId);
        return;
    }

    // 確保只初始化一次
    if (videoStream) {
        console.log("Vision already running.");
        return;
    }

    // 1. 請求攝影機權限
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            videoStream = stream;
            const videoElement = document.createElement('video');
            videoElement.srcObject = stream;
            videoElement.autoplay = true;
            videoElement.style.width = '100%';
            videoElement.style.transform = 'scaleX(-1)'; // 鏡像翻轉
            videoContainer.innerHTML = ''; // 清空容器
            videoContainer.appendChild(videoElement);

            if (statusElement) statusElement.textContent = '攝影機已啟動';

            // 2. 建立 WebSocket 連線
            // 注意：URL 需要根據你的 FastAPI 伺服器位址進行調整
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${window.location.host}/vision/ws/vision/${sessionId}`;
            
            websocket = new WebSocket(wsUrl);

            websocket.onopen = () => {
                console.log("WebSocket connection established.");
                if (statusElement) statusElement.textContent = '情緒分析連線成功！';
                
                // 3. 定期傳送影像幀
                frameInterval = setInterval(() => {
                    sendFrame(videoElement, sessionId);
                }, 1500); // 每 1.5 秒傳送一次
            };

            websocket.onmessage = (event) => {
                // 可選：處理來自後端的訊息 (例如，顯示偵測到的情緒)
                const data = JSON.parse(event.data);
                console.log("Received from server:", data);
                if (data.status === 'processed' && data.emotion && data.emotion.emotion) {
                     if (statusElement) statusElement.textContent = `即時情緒: ${data.emotion.emotion} (${data.emotion.confidence.toFixed(2)})`;
                }
            };

            websocket.onerror = (error) => {
                console.error("WebSocket error:", error);
                if (statusElement) statusElement.textContent = '連線錯誤';
            };

            websocket.onclose = () => {
                console.log("WebSocket connection closed.");
                if (statusElement) statusElement.textContent = '連線已中斷';
                stopVision(videoContainerId, statusElementId); // 清理資源
            };
        })
        .catch(err => {
            console.error("Error accessing camera:", err);
            if (statusElement) statusElement.textContent = '無法啟動攝影機';
        });
}

// 停止視覺分析功能
function stopVision(videoContainerId, statusElementId) {
    console.log("Stopping vision.");
    const videoContainer = document.getElementById(videoContainerId);
    const statusElement = document.getElementById(statusElementId);

    // 停止傳送影像幀
    if (frameInterval) {
        clearInterval(frameInterval);
        frameInterval = null;
    }

    // 關閉 WebSocket
    if (websocket) {
        websocket.close();
        websocket = null;
    }

    // 停止攝影機串流
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }

    // 清理 UI
    if (videoContainer) {
        videoContainer.innerHTML = '<p style="text-align:center; color:grey;">攝影機已關閉</p>';
    }
    if (statusElement) {
        statusElement.textContent = '視覺分析已停止';
    }
}

// 傳送單一影像幀
function sendFrame(videoElement, sessionId) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const canvas = document.createElement('canvas');
        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;
        const context = canvas.getContext('2d');
        context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
        
        // 將影像轉換為 Base64 字串
        const imageData = canvas.toDataURL('image/jpeg', 0.7).split(',')[1];

        // 透過 WebSocket 傳送
        websocket.send(JSON.stringify({
            image_data: imageData,
            session_id: sessionId
        }));
    }
}
