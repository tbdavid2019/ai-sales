---
title: AI Sales Multi-Agent System
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app_hf_spaces.py
pinned: false
license: mit
---

# AI Sales Multi-Agent System

一個基於多 Agent 架構的 AI 銷售助理系統，提供智能對話、名片識別、行事曆管理等功能。

## 🚀 功能特色

- **多 Agent 協作**：智能路由系統，自動選擇最適合的 Agent 處理請求
- **名片識別**：上傳名片圖片，自動提取姓名、職稱、公司等資訊
- **行事曆整合**：查詢空檔、安排會議（Mock 模式）
- **智能對話**：基於 Gemini 和 GPT 的自然語言處理
- **記憶功能**：記住對話歷史和用戶資料

## 🎯 使用方法

1. **一般對話**：直接在輸入框中輸入問題
2. **產品查詢**：詢問產品功能、價格、規格等
3. **名片識別**：點擊「上傳名片」按鈕上傳名片圖片
4. **行事曆查詢**：詢問時間相關問題，如「明天下午有空嗎？」

## 🛠️ 技術架構

- **前端**：Gradio Web UI
- **後端**：FastAPI + LangChain
- **AI 模型**：Gemini 2.5 Flash、GPT-4
- **記憶管理**：內建記憶體儲存（適配 Hugging Face Spaces）
- **Agent 協作**：自定義工作流管理器

## 📝 範例對話

```
用戶：你好，我想了解你們的產品
AI：您好！我是 AI 銷售助理，很高興為您服務。請問您想了解哪方面的產品資訊？

用戶：[上傳名片]
AI：王小明總監您好！我已經記住您的資訊。請問方便為您安排會議嗎？

用戶：明天下午有空嗎？
AI：讓我為您查詢明天下午的空檔... [查詢結果]
```

## 🔧 部署資訊

本系統已針對 Hugging Face Spaces 環境進行優化：
- 自動降級到內建記憶體儲存
- 支援 Mock 模式的外部服務整合
- 優化的資源使用和效能

## 📄 授權

MIT License
