# AIbusiness — 量化 AI 助手

> 模块化调用市场实时信息接口与网络搜索接口，接入 DeepSeek v4-pro 模型做解读输出。
> 独立完成的 Vibe Coding 项目：全程在 AI 辅助下从 0 到 1 搭建。

## 项目做了什么

一个「量化投资 AI 助手」：把 A 股行情、技术指标、宏观数据、联网搜索等**多个数据源做成模块化工具**，交给 DeepSeek v4-pro 模型自主调度——用户用自然语言提问，模型自己决定调用哪些数据接口，把数据拿回来后再生成带来源标注的分析结论。

核心能力：

- **多数据源模块化接入**：Baostock（A股历史行情/财务）、AKShare、Ashare（实时行情）、MyTT（50+ 技术指标）、easy_tdx（毫秒级行情）、OpenBB（全球市场）、AnySearch / SearXNG（联网搜索）等，通过统一的 `data_sources` + `tools` 架构注册与管理。
- **模型自主工具调用**：基于 OpenAI SDK 接入 DeepSeek v4-pro，实现 Function Calling，支持最多 8 轮多工具联动——模型先查本地数据，不足时自动切换联网搜索。
- **来源透明**：每次分析强制标注【本地数据库】/【公开网络信息】，避免模型编造数据。
- **思考链可视化**：展示模型的 reasoning 过程，便于观察"模型是如何决策的"。

## 技术栈

- Python 3.11
- OpenAI SDK（DeepSeek API）
- python-dotenv（密钥管理，不硬编码）
- 数据源：Baostock / AKShare / Ashare / MyTT / easy_tdx / OpenBB
- 搜索：AnySearch / SearXNG

## 目录结构

```
量化AI助手/
├── quant/
│   └── market_dpv4pro.py            # 主对话脚本：模型接入 + 工具调用循环
├── datasource_manager/
│   └── datasource_manager.py        # 数据源元数据管理（注册/下载/缓存文档）
├── .env.example                     # 密钥配置模板（复制为 .env 后填自己的 key）
├── .gitignore
└── README.md
```

> 说明：本仓库为**精简展示版**，只保留最能体现核心思路的两个文件，完整项目在私有仓库维护。API Key 通过 `.env` 配置，仓库中不含任何真实密钥。

## 核心实现要点

### 1. 模型接入与工具调用循环（`quant/market_dpv4pro.py`）

- 通过 `OpenAI(api_key=..., base_url="https://api.deepseek.com")` 接入 DeepSeek；
- 配置 `SYSTEM_PROMPT` 约束模型行为（诚实、工具优先、来源透明、风险提示）；
- 主循环 `chat_with_ai` 实现多轮工具调用：模型返回 tool_calls → 执行工具 → 结果回填 → 再问模型，直至产出最终答案（上限 8 轮）。

### 2. 数据源管理（`datasource_manager/datasource_manager.py`）

- 集中注册 8 个数据源的元信息（名称、文档地址、缓存文件、更新周期）；
- 提供文档自动下载、缓存、过期更新、动态查询帮助等能力；
- 让模型在不确定数据源用法时，能主动调用 `get_datasource_info` 查文档。

## 如何运行（可选）

```bash
# 1. 安装依赖
pip install openai python-dotenv requests baostock akshare

# 2. 配置密钥
copy .env.example .env   # 然后填入真实 API Key

# 3. 运行
python quant/market_dpv4pro.py
```

> 精简版仅含主流程代码，完整依赖与工具模块见私有仓库。
