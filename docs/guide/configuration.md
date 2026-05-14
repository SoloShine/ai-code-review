---
title: "配置说明"
---

# 配置说明

## 配置文件位置

AI Code Review 使用 YAML 格式的配置文件。项目级配置文件为项目根目录下的 `.ai-review.yaml`。

运行 `ai-review init` 时会自动生成一份默认配置，你可以根据项目需求进行调整。

## 完整配置项

以下是一份包含所有可配置项的完整示例：

```yaml
# 审查模式：balanced（均衡）或 strict（严格）
mode: "balanced"

# LLM 后端配置
llm:
  # 后端类型：ollama 或 openai_compatible
  backend: "openai_compatible"

  # Ollama 本地部署配置
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5-coder:7b"
    timeout: 60

  # OpenAI 兼容 API 配置（智谱、DeepSeek 等）
  openai_compatible:
    base_url: "https://open.bigmodel.cn/api/coding/paas/v4"
    api_key_env: "ZHIPU_API_KEY"
    model: "glm-5-turbo"
    timeout: 60

# Git Hooks 配置
hooks:
  # Pre-commit 钩子：提交前快速筛查
  pre_commit:
    timeout: 30
    block_on: ["CRITICAL", "ERROR"]
    rules_filter:
      severities: ["error"]
    bypass_env_vars: []

  # Post-commit 钩子：提交后深度审查
  post_commit:
    enabled: true

# 记忆系统配置
memory:
  enabled: true
  risk_threshold: 5

# 仪表盘配置
dashboard:
  auto_open: true

# 排除文件模式
exclude:
  - "*.lock"
  - "*.min.js"
  - "node_modules/"
  - "__pycache__/"
```

## 模式说明

AI Code Review 提供两种内置模式，覆盖大多数使用场景：

| 模式 | Pre-commit 行为 | Post-commit 行为 | 记忆系统 |
| ---- | --------------- | ---------------- | -------- |
| `balanced` | 仅拦截 ERROR/CRITICAL，超时 30 秒 | 启用 | 启用 |
| `strict` | 拦截所有级别，超时 60 秒 | 禁用 | 禁用 |

- **balanced**：日常开发推荐。Pre-commit 仅对严重问题阻断，不影响开发节奏；Post-commit 异步完成深度审查。
- **strict**：适合代码入库前的最终检查。所有级别问题均会拦截，确保代码质量。

## 配置层级

配置按以下优先级从低到高加载，高优先级覆盖低优先级：

1. **模式默认值** — `balanced` 或 `strict` 模式的内置默认配置
2. **用户全局配置** — `~/.ai-review/config.yaml`
3. **项目级配置** — 项目根目录下的 `.ai-review.yaml`

加载时采用 **深度合并（deep merge）** 策略。即：高优先级的配置项会覆盖同名键值，而未指定的配置项则继承低优先级的值。

:::tip 示例
如果你在全局配置中设定了 `llm.backend: "ollama"`，但在项目的 `.ai-review.yaml` 中指定了 `llm.openai_compatible.model: "glm-5-turbo"`，则最终生效的配置中 `backend` 为 `ollama`，同时保留 `openai_compatible` 下的 `model` 设置。
:::

## 环境变量

以下环境变量用于配置 API 密钥和运行模式：

| 环境变量 | 说明 |
| -------- | ---- |
| `ZHIPU_API_KEY` | 智谱 AI API 密钥，用于 `openai_compatible` 后端连接智谱服务 |
| `OPENAI_API_KEY` | OpenAI API 密钥，用于直接连接 OpenAI 或兼容服务 |
| `AI_REVIEW_MODE` | 运行模式覆盖，值为 `balanced` 或 `strict`，优先级高于配置文件 |

:::warning 安全提示
请勿将 API 密钥硬编码在配置文件中。所有密钥应通过环境变量注入。推荐使用 `.env` 文件或系统密钥管理工具，并将 `.env` 加入 `.gitignore`。
:::
