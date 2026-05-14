---
title: "快速开始"
---

# 快速开始

本指南将帮助你在几分钟内完成 AI Code Review 工具的安装和配置，开始享受智能代码审查。

## 安装

通过 pip 安装 AI Code Review：

```bash
pip install soloshine-ai-code-review
```

安装完成后，验证是否成功：

```bash
ai-review --help
```

:::tip
建议在虚拟环境中安装，避免与系统 Python 包产生冲突。可以使用 `venv` 或 `conda` 创建独立环境。
:::

## 初始化项目

进入你的项目目录，运行初始化命令：

```bash
cd your-project
ai-review init
```

初始化过程会自动完成以下工作：

- 创建配置文件 `.ai-review.yaml`，用于定义审查策略和 LLM 后端
- 创建 `.ai-review/` 目录，其中包含 `rules/` 子目录，用于存放自定义审查规则
- 安装 Git 钩子：
  - **pre-commit 钩子**：在每次提交前自动运行快速审查，拦截包含严重问题的提交
  - **post-commit 钩子**：在提交完成后异步执行全面审查，生成详细报告

:::warning
确保你的项目已经是一个 Git 仓库（已执行过 `git init`），否则钩子安装会失败。
:::

## 配置 LLM 后端

AI Code Review 支持多种 LLM 后端。编辑 `.ai-review.yaml` 文件进行配置。

### 选项 A：智谱 GLM（推荐国内用户使用）

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

:::tip
使用智谱 GLM 前，请先设置环境变量：
```bash
export ZHIPU_API_KEY="your-api-key-here"
```
在 `api_key_env` 中填入环境变量名称，工具会自动读取，避免将密钥硬编码在配置文件中。
:::

### 选项 B：Ollama（本地部署）

首先启动 Ollama 服务并拉取模型：

```bash
ollama serve
ollama pull qwen2.5-coder:7b
```

然后在 `.ai-review.yaml` 中配置：

```yaml
mode: "balanced"
llm:
  backend: "ollama"
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5-coder:7b"
    timeout: 60
```

:::tip
本地部署适合对数据隐私有较高要求的场景，且无需联网即可使用。推荐至少使用 7B 参数量的代码专用模型以获得较好的审查质量。
:::

## 添加审查规则

在 `.ai-review/rules/` 目录下创建 YAML 规则文件，定义你的代码审查规则：

```yaml
name: "Frontend Code Rules"
rules:
  - id: "no-console-log"
    title: "禁止提交 console.log 调试语句"
    severity: "warning"
    enabled: true
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "console.log 调试语句不应提交到代码库"
```

规则字段说明：

| 字段 | 说明 |
|------|------|
| `id` | 规则唯一标识符 |
| `title` | 规则标题，会显示在审查报告中 |
| `severity` | 严重程度，支持 `error`、`warning`、`info` |
| `enabled` | 是否启用该规则 |
| `applies_to` | 规则适用范围，可按文件扩展名过滤 |
| `description` | 规则描述，帮助 LLM 理解审查意图 |

:::warning
`severity` 设置为 `error` 的规则一旦触发，将阻止代码提交（pre-commit 钩子会拦截）。请谨慎使用，避免影响正常开发流程。
:::

## 提交代码触发审查

配置完成后，审查会在你提交代码时自动触发：

```bash
git add .
git commit -m "feat: add user component"
```

执行流程如下：

1. **pre-commit 阶段**：自动运行快速审查，检查暂存区中的文件变更。如果发现 `severity: error` 级别的问题，提交将被阻止，你需要修复后重新提交。
2. **post-commit 阶段**：提交成功后，异步执行全面的代码审查，生成详细报告并存入收件箱，不会阻塞你的工作流。

:::tip
如果需要临时跳过审查（不推荐），可以使用 `git commit --no-verify`。但这会同时跳过所有 Git 钩子，请谨慎使用。
:::

## 查看审查结果

使用以下命令查看和管理审查报告：

```bash
# 查看收件箱中所有审查报告
ai-review inbox

# 查看指定报告的详细内容
ai-review inbox show <report-id>

# 查看审查仪表盘（汇总统计）
ai-review inbox dashboard
```

:::tip
建议定期运行 `ai-review inbox` 查看审查结果，及时处理发现的问题。审查报告会按时间排序，最新的报告排在最前面。
:::
