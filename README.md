# PlaywrightsPen (剧作家之笔) 🎭

> **The first MCP-native automation framework designed for the "LLM + Desktop" era.**

PlaywrightsPen (剧作家之笔) 是一个原生支持 **Model Context Protocol (MCP)** 的智能化自动化测试与任务编排服务。它不仅能像人类一样理解网页，更是目前开源界极少数能够**原生驱动本地 Electron 桌面应用**的 AI 代理框架。

### 🌟 核心亮点

- 🖥️ **本地桌面端支持**：通过 Playwright 深度注入，原生支持对本地 Electron 应用（如 VS Code、Slack、自定义桌面客户端）进行 AI 自动化控制。
- ⚡ **极速 & 语义化**：基于 **Accessibility Tree (辅助功能树)** 而非截图。Token 消耗降低 90%+，动作识别精准度提升 2x。
- 🤖 **原生 MCP 架构**：无缝连接 Claude Desktop、Cursor、Windsurf 等 AI 开发环境，让 AI 真正拥有“手和眼睛”。
- 🔒 **隐私与安全**：支持私有化部署 LLM，数据和测试会话完全由你控制。

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

## 🚀 路线图 & TODO List

我们的目标是将 PlaywrightsPen 打造为最强大的 AI 桌面/Web 编排引擎。欢迎认领任务！

### 🛠️ 近期计划 (Short-term)
- [ ] **可视化录制器优化**：支持在录制 Electron 应用时自动生成自然语言描述。
- [ ] **多模型适配**：深度优化对 DeepSeek-V3 和 Claude 3.5 Sonnet 的 Prompt 模板。
- [ ] **Docker 一键部署**：提供标准的 Docker Compose 文件，简化环境配置。

### 📈 中期目标 (Mid-term)
- [ ] **自愈测试 (Self-healing)**：当 UI 变动导致定位失败时，AI 自动尝试修复执行路径。
- [ ] **多 Session 协同**：支持在一个测试任务中跨多个浏览器上下文（甚至跨 Web 和 Electron）进行协作。
- [ ] **Web 控制面板**：一个精美的可视化后台，用于管理测试用例、查看执行回放和截图。

### 🌌 长期愿景 (Long-term)
- [ ] **插件系统**：支持开发者为特定的 Electron 应用编写专有的“动作插件”。
- [ ] **离线 VLM 支持**：集成轻量级本地视觉模型，作为辅助功能树失效时的补充方案。

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
