# LearnAI - Coding Agent

一个基于 Claude API 打造的互动式程式码助理 Agent，支援读取、列出、编辑档案等工具呼叫。

## 功能

- 与 Claude 进行多轮对话
- 支援工具呼叫：读档案、列目錄、编辑档案
- 自动解析模型输出中的工具指令并执行
- 彩色终端输出（使用者蓝色 / AI 黄色）

## 工具清单

| 工具 | 說明 |
|------|------|
| `read_file` | 读取指定档案的完整内容 |
| `list_files` | 列出资料夹下所有档案与子资料夹 |
| `edit_file` | 新建或编辑档案内容 |

## 安装

```bash
# 安装依赖
 pip install anthropic python-dotenv
```

## 設定

在 `env.json` 中填入你的 Anthropic API 金鑰：

```json
{
  "ANTHROPIC_AUTH_TOKEN": "your-api-key-here"
}
```

## 執行

```bash
python completed_code.py
```

啟動後直接在終端輸入問題，Agent 會自动判斷是否需要呼叫工具來完成任务。

## 專案結構

```
LearnAI/
├── completed_code.py   # 主程式：Agent 迴圈 + 工具定義
├── env.json            # API 金鑰設定
├── env.sh              # 環境變數腳本
├── pyproject.toml      # 專案依赖設定
└── README.md           # 專案說明
```

## 注意事項

- `env.json` 包含敏感金鑰，請勿提交至公開儲存庫
- 建議將 `env.json` 加入 `.gitignore`
