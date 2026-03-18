# PlaywrightsPen (剧作家之笔)

> Natural language automated testing service powered by Playwright MCP

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🎭 概述

PlaywrightsPen 是一个基于 Playwright MCP 的智能化自动化测试服务。通过自然语言描述测试用例，结合大语言模型（LLM）的能力，实现：

- 🗣️ **自然语言测试** - 用中文或英文描述测试场景
- 🖥️ **支持 Electron/桌面端** - 唯一原生支持对本地 Electron 应用进行 AI 自动化的 MCP 服务
- 🔄 **交互式首轮执行** - 首次运行时支持人工确认关键步骤
- 🎯 **智能回归测试** - 基于首轮执行记录自动化后续回归
- ⚡ **原生 MCP 支持** - 与 Claude Desktop、Cursor、Windsurf 等 AI 工具极速集成
- 🔒 **私有化部署** - 数据不外泄，支持自定义模型

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
cd playwrights_pen

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -e .

# 安装 Playwright 浏览器
playwright install chromium
```

### 配置

复制环境变量示例文件并配置：

```bash
copy .env.example .env
```

编辑 `.env` 文件：

```env
# LLM 配置 (OpenAI 兼容接口)
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# 浏览器配置
BROWSER_HEADLESS=false
```

### 使用 CLI

```bash
# 运行一个自然语言测试
playwrights-pen run "打开百度，搜索Playwright，验证搜索结果页面包含Playwright"

# 指定确认模式
playwrights-pen run "..." --confirm every_step   # 每步确认
playwrights-pen run "..." --confirm key_steps    # 仅关键步骤确认
playwrights-pen run "..." --confirm none         # 完全自动

# 查看测试用例列表
playwrights-pen list-cases

# 查看执行会话
playwrights-pen list-sessions

# 查看配置
playwrights-pen config
```

### 使用 REST API

启动 API 服务器：

```bash
playwrights-pen serve
# 或
uvicorn playwrights_pen.main:app --reload
```

访问 API 文档：`http://localhost:8000/docs`

#### 示例请求

```bash
# 创建测试用例
curl -X POST http://localhost:8000/api/v1/testcases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "百度搜索测试",
    "description": "打开百度首页，搜索Playwright，验证结果",
    "parse_now": true
  }'

# 执行测试
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "xxx",
    "mode": "exploration",
    "confirmation_mode": "key_steps"
  }'
```

## 📁 项目结构

```
playwrights_pen/
├── src/playwrights_pen/
│   ├── api/              # REST API 端点
│   ├── core/             # 核心模块
│   │   ├── parser.py     # 自然语言解析
│   │   ├── orchestrator.py  # 测试编排
│   │   ├── executor.py   # 执行引擎
│   │   └── recorder.py   # 执行记录
│   ├── llm/              # LLM 客户端
│   ├── mcp/              # MCP 客户端
│   ├── models/           # 数据模型
│   ├── storage/          # 存储层
│   ├── cli.py            # 命令行界面
│   ├── config.py         # 配置管理
│   └── main.py           # FastAPI 入口
├── data/                 # 运行时数据
├── pyproject.toml
└── README.md
```

## 🔧 确认模式说明

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `every_step` | 每个步骤都需确认 | 首次探索新流程 |
| `key_steps` | 仅关键步骤确认（如提交、删除） | 日常使用推荐 |
| `none` | 完全自动执行 | 回归测试、CI/CD |

## 🌟 为什么选择 PlaywrightsPen?

与基于视觉 (Vision-based) 的代理（如 Skyvern）相比，PlaywrightsPen 采用 **Accessibility Tree (辅助功能树)** 方案：
- **更精准**：直接操作 DOM 和语义节点，避免视觉偏移引起的问题。
- **更省钱**：由于不传输截图，Token 消耗降低 90% 以上。
- **支持桌面端**：原生支持本地 **Electron** 应用的自动化。

## 🤝 参与贡献

我们欢迎所有形式的贡献！无论你是想修复 Bug、增加新功能，还是改进文档：
1. 查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发指引。
2. 欢迎在 [Issues](https://github.com/your-username/playwrights_pen/issues) 中提出你的想法。

## 📜 License

MIT License

## 🔗 相关链接

- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Playwright Python](https://playwright.dev/python/)
