# AI Code Review 使用手册

> AI 驱动的代码审查工具，支持 Git Hook 集成、自定义规则、LLM 审查、通知中心

---

## 目录

- [概述](#概述)
- [安装](#安装)
- [快速开始](#快速开始)
- [配置](#配置)
- [命令参考](#命令参考)
- [规则系统](#规则系统)
- [通知中心](#通知中心)
- [抑制系统](#抑制系统)
- [项目结构](#项目结构)
- [注意事项](#注意事项)

---

## 概述

AI Code Review 是一个本地运行的代码审查工具，通过接入 LLM（大语言模型）对代码变更进行智能审查。核心能力：

| 能力 | 说明 |
|------|------|
| **Pre-commit 拦截** | 提交前快速筛查，发现严重问题直接阻止提交 |
| **Post-commit 深度审查** | 提交后异步执行完整审查，生成详细报告 |
| **智能文件分组** | 大文件单独审查，小文件合并请求，自动平衡 LLM 调用次数和上下文质量 |
| **Diff 三明治截断** | 超大 diff 保留头尾关键代码，中间用摘要替代，避免丢失边界上下文 |
| **自定义规则** | YAML 格式规则文件，按文件类型自动匹配 |
| **记忆系统** | 跨次审查跟踪重复问题，计算风险分数 |
| **通知中心** | 终端 Inbox + HTML 仪表盘 + 系统弹窗三通道提醒 |
| **抑制管理** | 对已知且暂不处理的问题标记抑制，停止弹窗干扰 |

支持的 LLM 后端：

- **Ollama** — 本地部署，无需 API Key
- **OpenAI Compatible** — 任何兼容 OpenAI 接口的服务（智谱 GLM、DeepSeek、通义千问等）

---

## 安装

### 环境要求

- Python >= 3.10
- Git
- LLM 后端（Ollama 或 OpenAI 兼容 API）

### 安装步骤

```bash
# 从 PyPI 安装
pip install soloshine-ai-code-review

# 验证安装
ai-review --help
```

### 依赖说明

核心依赖（pip install 时自动安装）：

| 包 | 用途 |
|----|------|
| `typer` | CLI 框架 |
| `httpx` | LLM API 调用 |
| `pyyaml` | 配置和规则文件解析 |
| `rich` | 终端美化输出 |

---

## 使用 AI Agent 一键配置（推荐）

本项目提供了 Skill 安装器，可以让你的 AI coding agent 自动完成全套安装和配置，无需手动操作。

支持的 Agent：Claude Code、Cursor、GitHub Copilot、Windsurf、Cline、OpenCode、Aider

```bash
# 克隆仓库后运行安装器
git clone https://github.com/SoloShine/ai-code-review.git
python ai-code-review/skills/install_skill.py
```

安装完成后，在你的 AI agent 中打开任意项目，说「帮我配置代码审查」即可自动完成 pip 安装、LLM 后端配置、审查规则生成、Git hooks 安装。

详见 [skills/README.md](skills/README.md)。

---

## 快速开始

### 1. 在项目中初始化

```bash
cd your-project
ai-review init
```

该命令会：
- 创建 `.ai-review.yaml` 配置文件
- 创建 `.ai-review/` 目录结构（含 `rules/` 子目录）
- 安装 Git pre-commit 和 post-commit 钩子
- 自动更新 `.gitignore`（忽略生成文件，保留 `rules/` 供版本控制）

### 2. 配置 LLM 后端

编辑 `.ai-review.yaml`，选择后端：

**使用智谱 GLM（推荐国内用户）：**

```yaml
mode: "balanced"
llm:
  backend: "openai_compatible"
  openai_compatible:
    base_url: "https://open.bigmodel.cn/api/coding/paas/v4"
    api_key_env: "ZHIPU_API_KEY"
    model: "glm-5-turbo"
    timeout: 60
```

然后设置环境变量：

```bash
# Linux/macOS
export ZHIPU_API_KEY="your-api-key"

# Windows PowerShell
[Environment]::SetEnvironmentVariable("ZHIPU_API_KEY", "your-api-key", "User")
```

**使用 Ollama（本地部署）：**

```bash
# 先启动 Ollama 服务
ollama serve
ollama pull qwen2.5-coder:7b
```

```yaml
mode: "balanced"
llm:
  backend: "ollama"
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5-coder:7b"
    timeout: 60
```

### 3. 添加审查规则

在 `.ai-review/rules/` 下创建 YAML 规则文件，例如 `frontend-rules.yaml`：

```yaml
name: "Frontend Code Rules"
description: "Vue/TypeScript frontend review rules"
rules:
  - id: "no-console-log"
    title: "禁止提交 console.log 调试语句"
    severity: "warning"
    enabled: true
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "console.log 调试语句不应提交到代码库，应使用项目中的 logger 工具替代。"

  - id: "no-any-type"
    title: "禁止使用 any 类型"
    severity: "warning"
    enabled: true
    applies_to:
      extensions: [".ts", ".tsx"]
    description: "TypeScript 中使用 any 会导致类型检查失效，应使用具体类型或泛型替代。"
```

### 4. 提交代码触发审查

```bash
# 正常提交代码
git add .
git commit -m "feat: add user component"

# pre-commit hook 会自动运行快速筛查
# 如果发现 ERROR 级别问题，提交会被阻止
# 如果通过，post-commit hook 会异步执行完整审查
```

### 5. 查看审查结果

```bash
# 查看未读报告
ai-review inbox

# 查看某份报告详情
ai-review inbox show <report-id>

# 打开 HTML 仪表盘
ai-review inbox dashboard
```

---

## 配置

配置文件为项目根目录的 `.ai-review.yaml`。

### 完整配置项

```yaml
# ==================== 基础设置 ====================

# 运行模式: "balanced"（平衡，推荐） | "strict"（严格）
mode: "balanced"

# ==================== LLM 后端 ====================

llm:
  # 选择后端: "ollama" | "openai_compatible"
  backend: "openai_compatible"

  # Ollama 后端配置
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5-coder:7b"
    timeout: 60

  # OpenAI 兼容后端配置
  openai_compatible:
    base_url: "https://open.bigmodel.cn/api/coding/paas/v4"
    api_key_env: "ZHIPU_API_KEY"     # API Key 环境变量名
    model: "glm-5-turbo"
    timeout: 60

# ==================== Git Hook ====================

hooks:
  pre_commit:
    timeout: 60                       # 快速筛查超时（秒）
    block_on: ["CRITICAL", "ERROR"]   # 遇到这些级别的问题阻止提交
    rules_filter:
      severities: ["error"]           # pre-commit 只检查 error 级别规则
    bypass_env_vars: []               # 设置这些环境变量可跳过审查

  post_commit:
    enabled: true                     # 启用 post-commit 异步审查

# ==================== 记忆系统 ====================

memory:
  enabled: true                       # 启用记忆系统
  risk_threshold: 5                   # 风险分数阈值（0-10）
  # reminder: 提醒策略（内部使用）

# ==================== 仪表盘 ====================

dashboard:
  auto_open: true                     # 异步审查完成后自动打开浏览器

# ==================== 排除规则 ====================

exclude:
  - "*.lock"
  - "*.min.js"
  - "*.min.css"
  - "*.png"
  - "*.jpg"
  - "package-lock.json"
  - "node_modules/"
  - "dist/"
  - "__pycache__/"
```

### 模式说明

| 模式 | Pre-commit | Post-commit | Memory | 说明 |
|------|-----------|-------------|--------|------|
| **balanced** | 仅筛查 ERROR/CRITICAL，60s 超时 | 启用 | 启用 | 推荐日常使用 |
| **strict** | 筛查所有级别（含 WARNING），90s 超时 | 禁用 | 禁用 | 严格模式，适合关键分支 |

---

## 命令参考

### `ai-review init`

初始化项目，创建配置文件和安装 Git 钩子。

```bash
ai-review init [--mode balanced] [--backend ollama] [--model qwen2.5-coder:7b]
```

### `ai-review check`

执行代码审查，支持三种模式。

**Pre-commit 模式**（由 Git Hook 自动调用）：

```bash
ai-review check --pre-commit [--no-block]
```

**异步 Post-commit 模式**（由 Git Hook 自动调用）：

```bash
ai-review check --async --commit <sha> [--open-dashboard]
```

**手动审查模式**：

```bash
# 审查当前暂存区
ai-review check

# 审查指定文件
ai-review check --path src/app.py

# 与分支对比审查
ai-review check --base main

# 详细输出
ai-review check --verbose

# 调试模式（显示 prompt 和 LLM 原始响应）
ai-review check --debug --verbose
```

**选项说明：**

| 选项 | 说明 |
|------|------|
| `--pre-commit` | 以 pre-commit hook 模式运行（快速筛查） |
| `--async` | 异步 post-commit 审查模式 |
| `--commit <sha>` | 指定审查的 commit（异步模式必需） |
| `--base <branch>` | 与指定分支对比审查 |
| `--path <file>` | 审查指定文件 |
| `--no-block` | 仅报告，不阻止提交 |
| `--verbose`, `-v` | 显示详细输出 |
| `--debug` | 显示调试信息（prompt、LLM 原始响应） |
| `--open-dashboard` | 审查完成后打开 HTML 仪表盘 |

### `ai-review inbox`

管理审查报告通知中心。

```bash
# 列出所有报告（默认命令）
ai-review inbox
ai-review inbox --unread              # 仅显示未读
ai-review inbox --status WARNING      # 按状态筛选
ai-review inbox --limit 10            # 限制数量
ai-review inbox --all                 # 包含已归档

# 查看报告详情（自动标记已读）
ai-review inbox show <report-id>
ai-review inbox show <report-id> --md # 在浏览器中打开 Markdown 报告

# 标记已读/未读
ai-review inbox read <report-id>
ai-review inbox unread <report-id>
ai-review inbox mark-all-read

# 生成并打开 HTML 仪表盘
ai-review inbox dashboard
```

### `ai-review suppress`

管理规则抑制（对特定文件跳过特定规则的弹窗通知）。

```bash
# 查看已抑制的规则
ai-review suppress --list

# 抑制某个文件的特定规则
ai-review suppress src/utils/helper.ts no-console-log --reason "调试阶段暂保留"

# 抑制某个文件的所有规则
ai-review suppress src/legacy/old.ts --all --reason "遗留代码，暂不处理"

# 取消抑制
ai-review suppress src/utils/helper.ts no-console-log --cancel
ai-review suppress src/legacy/old.ts --all --cancel
```

> **注意**：抑制不会阻止审查本身，报告仍会包含这些问题，只是不再弹窗通知。

### `ai-review status`

查看高风险文件和待处理警告。

```bash
ai-review status
```

### `ai-review config-show`

显示当前生效的完整配置。

```bash
ai-review config-show
```

---

## 规则系统

### 规则文件格式

在 `.ai-review/rules/` 目录下创建 YAML 文件，支持多个规则文件：

```yaml
name: "规则集名称"
description: "规则集描述"
rules:
  - id: "rule-id"                   # 唯一标识符
    title: "规则标题"                # 简短描述
    severity: "error"                # 级别: error | warning | info
    enabled: true                    # 是否启用
    applies_to:
      extensions: [".py", ".js"]     # 适用的文件扩展名
    description: "详细描述规则内容，LLM 会参考此描述进行审查。"

  # 更多规则...
```

### 规则字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 规则唯一标识，用于抑制管理和报告引用 |
| `title` | 是 | 规则简短标题 |
| `severity` | 是 | `error`（阻止提交）/ `warning`（仅警告）/ `info`（提示） |
| `enabled` | 否 | 默认 `true`，设为 `false` 禁用 |
| `applies_to.extensions` | 否 | 适用的文件扩展名列表 |
| `applies_to.paths` | 否 | 适用的文件路径 glob 模式 |
| `description` | 是 | 规则详细描述，LLM 参考此内容审查 |

### Severity 与 Pre-commit 行为

| Severity | Pre-commit 行为 | Post-commit 行为 |
|----------|----------------|-----------------|
| `error` | 匹配到即阻止提交 | 报告为 ERROR 级别 |
| `warning` | 不阻止提交 | 报告为 WARNING 级别 |
| `info` | 不参与筛查 | 报告为 INFO 级别 |

> 默认配置下，`pre_commit.rules_filter.severities` 为 `["error"]`，即只有 `severity: "error"` 的规则参与 pre-commit 筛查。如果需要更严格的筛查，可改为 `["error", "warning"]`。

### 规则示例

**前端 TypeScript/Vue 规则：**

```yaml
name: "Vue Frontend Rules"
rules:
  - id: "no-settimeout"
    title: "禁止使用 setTimeout"
    severity: "error"
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "禁止使用 setTimeout 处理时序性问题，应使用 Promise/nextTick 等可靠机制。"

  - id: "promise-catch"
    title: "Promise 必须处理错误"
    severity: "error"
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "所有 Promise 链必须包含 .catch() 或使用 try/catch 包裹 async/await。"

  - id: "no-console-log"
    title: "禁止提交 console.log"
    severity: "warning"
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "console.log 调试语句不应提交到代码库，应使用项目中的 logger 工具替代。"

  - id: "no-any-type"
    title: "禁止使用 any 类型"
    severity: "warning"
    applies_to:
      extensions: [".ts", ".tsx"]
    description: "TypeScript 中使用 any 会导致类型检查失效，应使用具体类型或泛型替代。"
```

**后端 Python 规则：**

```yaml
name: "Python Backend Rules"
rules:
  - id: "no-eval"
    title: "禁止使用 eval"
    severity: "error"
    applies_to:
      extensions: [".py"]
    description: "禁止使用 eval，存在严重的代码注入安全风险。"

  - id: "sql-injection"
    title: "防止 SQL 注入"
    severity: "error"
    applies_to:
      extensions: [".py"]
    description: "禁止拼接 SQL 语句，必须使用参数化查询。"

  - id: "no-hardcoded-secrets"
    title: "禁止硬编码密钥"
    severity: "error"
    applies_to:
      extensions: [".py"]
    description: "禁止在代码中硬编码 API Key、密码等敏感信息，应使用环境变量。"
```

---

## 通知中心

通知中心提供三种互补的报告查看方式：

### 1. 系统弹窗（即时提醒）

每次审查完成后自动弹出 Windows/macOS/Linux 系统通知。适合快速获知审查结果。

- Windows：优先使用 BurntToast，回退到 BalloonTip
- 弹窗内容包含 issue 摘要
- 受抑制规则控制，被抑制的 issue 不触发弹窗

### 2. 终端 Inbox（日常浏览）

```bash
ai-review inbox                    # 列出报告
ai-review inbox --unread           # 仅看未读
ai-review inbox show <report-id>   # 查看详情（自动标记已读）
ai-review inbox mark-all-read      # 全部标记已读
```

在终端直接浏览、搜索、阅读报告。适合开发者日常工作流。

### 3. HTML 仪表盘（全景视图）

```bash
ai-review inbox dashboard          # 生成并打开仪表盘
```

自动生成 `.ai-review/reports/index.html`，在浏览器中打开。功能：

- 所有报告按时间倒序排列，状态分色标记
- 点击展开查看每个 issue 的详情和代码建议（diff 风格）
- 顶部搜索栏实时过滤
- 未读标记（蓝点）
- 深色主题，适配开发者审美

> 异步审查完成后，如果 `dashboard.auto_open` 为 `true`（默认），会自动在浏览器中打开仪表盘。

---

## 抑制系统

对于已知但暂不打算处理的问题，可以抑制其弹窗通知。

### 工作机制

抑制**不会**影响审查本身：
- 审查照常运行
- 报告照常生成（包含被抑制的问题）
- **仅跳过弹窗通知**

### 使用方法

```bash
# 抑制某个文件的某条规则
ai-review suppress src/legacy/old.ts no-eval --reason "遗留代码，计划 Q3 重构"

# 抑制某个文件的所有规则
ai-review suppress src/legacy/old.ts --all --reason "遗留模块，不做审查"

# 查看已抑制项
ai-review suppress --list

# 取消抑制
ai-review suppress src/legacy/old.ts no-eval --cancel
```

### 匹配规则

抑制匹配支持三级策略，解决 LLM 输出格式与规则 ID 不一致的问题：

1. **精确匹配** — 规则 ID 完全一致（忽略大小写和下划线/连字符差异）
2. **子串匹配** — 抑制的 ID 包含在 LLM 输出的 rule_id 中
3. **关键词匹配** — 从抑制 ID 中提取关键词（如 `no-console-log` → `console`, `log`），全部出现在 issue 消息中则匹配

---

## 项目结构

```
your-project/
├── .ai-review.yaml            # 项目配置文件
└── .ai-review/
    ├── memory.json             # 记忆数据（风险分数、抑制记录、inbox 状态）
    ├── rules/                  # 自定义审查规则
    │   ├── frontend.yaml
    │   ├── backend.yaml
    │   └── css-rules.yaml
    └── reports/                # 审查报告（自动生成）
        ├── index.html          # HTML 仪表盘
        ├── review_<tag>_<ts>.json
        └── review_<tag>_<ts>.md
```

### 源码结构

```
src/ai_review/
├── cli.py                     # 主 CLI 入口（check/init/suppress/status）
├── cli_inbox.py               # Inbox 子命令（inbox list/show/read/dashboard）
├── config.py                  # 配置系统（分层合并、模式默认值）
├── diff_utils.py              # Diff 拆分、智能分组、三明治截断
├── dashboard.py               # HTML 仪表盘生成器
├── inbox.py                   # Inbox 管理器（报告注册、已读状态）
├── memory/
│   └── store.py               # 记忆系统（风险分数、抑制、衰减）
├── llm/
│   ├── base.py                # LLM 提供者抽象接口
│   ├── ollama.py              # Ollama 本地后端
│   └── openai.py              # OpenAI 兼容后端
├── prompt/
│   └── builder.py             # Prompt 构建（fast/full 两种模式）
├── reviewer/
│   ├── screener.py            # Pre-commit 快速筛查器（智能分组审查）
│   └── parser.py              # LLM 输出解析（JSON 优先 + 文本回退）
├── rules/
│   ├── loader.py              # 规则加载和文件匹配
│   └── formatter.py           # 规则格式化（prompt/JSON/HTML）
├── hooks/
│   └── installer.py           # Git Hook 安装/卸载
└── output/
    ├── notify.py              # 系统通知（跨平台，三级回退）
    └── terminal.py            # Rich 终端格式化输出
```

---

## 注意事项

### 环境变量

| 变量 | 用途 | 示例 |
|------|------|------|
| `ZHIPU_API_KEY` | 智谱 API Key | `export ZHIPU_API_KEY="xxx"` |
| `OPENAI_API_KEY` | OpenAI API Key | 默认变量名，可通过 `api_key_env` 自定义 |
| `AI_REVIEW_MODE` | 覆盖运行模式 | `export AI_REVIEW_MODE="strict"` |

> Windows 用户设置环境变量后需**重启终端**才能生效，或使用：
> ```powershell
> [Environment]::SetEnvironmentVariable("ZHIPU_API_KEY", "your-key", "User")
> ```

### 编码问题

工具内部已处理 Windows GBK 编码问题（emoji 输出、子进程中文），无需额外配置。

### 性能

| 场景 | 典型耗时 | 说明 |
|------|---------|------|
| Pre-commit 筛查 | 5-15 秒 | 智能分组：大文件单独请求，小文件合并；仅 error 级别规则 |
| Post-commit 全量审查 | 10-30 秒 | 分组完整审查，返回详细报告和代码建议 |
| 手动审查 | 10-30 秒 | 同全量审查 |
| 批量重命名（200+ 文件） | < 1 秒 | 小文件自动合并，跳过文件数阈值直接放行 |

> Pre-commit 超时默认 60 秒，超时自动放行（不阻止提交）。大文件（>200 行）单独审查，小文件合并为单次 LLM 请求（最多 15 文件 / 500 行）。LLM 不可用时跳过剩余批次，不会逐个超时。可在配置中调整 `hooks.pre_commit.timeout`。

### LLM 故障处理

- Pre-commit：LLM 不可用时**自动放行**，不阻止提交
- Post-commit：LLM 不可用时**静默跳过**，不影响工作流
- 解析失败：LLM 返回无法解析的内容时**自动放行**

### 报告管理

- 报告存储在 `.ai-review/reports/` 下，每份报告包含 `.json`（机器可读）和 `.md`（人类可读）
- 建议将 `.ai-review/reports/` 加入 `.gitignore`，报告为本地开发辅助数据
- HTML 仪表盘每次审查后自动重新生成，始终反映最新状态

### 记忆系统衰减

- 警告记录 30 天后自动衰减清理
- 风险分数基于警告出现频率计算（0-10 分）
- 提醒策略随重复次数递减：完整 → 简短 → 最小 → 静默

### Windows 通知

系统弹窗依赖 Windows 通知服务：

- 推荐安装 BurntToast PowerShell 模块获得最佳体验：`Install-Module -Name BurntToast -Force -Scope CurrentUser`
- 如通知被系统设置屏蔽，工具会自动回退到终端输出
- 通知中心（inbox + dashboard）不依赖系统通知服务，始终可用

### 与 CI/CD 的关系

本工具定位为**本地开发辅助**，在开发者提交代码时提供即时反馈，不替代 CI/CD 中的代码审查流程。`ai-review init` 会自动更新 `.gitignore`，仅忽略生成文件：

```gitignore
# AI Code Review - generated files (rules/ are versioned)
.ai-review/memory.json
.ai-review/suppressions.json
.ai-review/reports/
```

`.ai-review/rules/` 目录下的规则文件会保留在版本控制中，方便团队共享审查规范。

### 常见问题

**Q: 提交时没有触发审查？**

检查 Git Hook 是否安装：

```bash
ls .git/hooks/pre-commit
ls .git/hooks/post-commit
```

如果不存在，运行 `ai-review init` 重新安装。

**Q: 审查超时了？**

Pre-commit 默认超时 60 秒。如果 LLM 响应较慢，可在 `.ai-review.yaml` 中增加超时：

```yaml
hooks:
  pre_commit:
    timeout: 90
```

**Q: 如何临时跳过审查？**

方法一：设置环境变量（如果配置了 `bypass_env_vars`）
方法二：使用 `--no-verify` 跳过 Git Hook（`git commit --no-verify`）

> 不推荐长期使用 `--no-verify`，应通过抑制系统处理已知问题。

**Q: 报告中 rule_id 是中文，抑制不生效？**

抑制系统支持模糊匹配，会从英文规则 ID 中提取关键词与 issue 消息内容匹配。如果仍不生效，检查 `ai-review suppress --list` 中存储的文件路径是否与报告中的路径一致。

**Q: 支持 GitLab / Bitbucket 吗？**

工具通过 Git 命令获取 diff 信息，与代码托管平台无关，任何 Git 仓库均可使用。
