---
title: "命令参考"
---

# 命令参考

AI Code Review 提供以下子命令，涵盖项目初始化、代码检查、通知管理和配置查看等完整工作流。

## ai-review init

初始化项目配置，在项目根目录生成 `.ai-review.yaml` 配置文件。

```bash
ai-review init
```

### 选项

| 选项 | 说明 |
| ---- | ---- |
| `--mode <mode>` | 审查模式，可选 `balanced` 或 `strict`，默认 `balanced` |
| `--backend <backend>` | LLM 后端类型，可选 `ollama` 或 `openai_compatible` |
| `--model <model>` | 指定模型名称，如 `glm-5-turbo`、`qwen2.5-coder:7b` |

:::tip 提示
如果项目根目录已存在 `.ai-review.yaml`，`init` 命令会询问是否覆盖。建议首次使用时先执行 `init`，再根据需要修改配置。
:::

## ai-review check

执行代码审查，支持三种运行模式。

### Pre-commit 快速筛查

在 Git pre-commit 钩子中调用，对暂存文件进行快速安全检查：

```bash
ai-review check --pre-commit
```

此模式仅检查 CRITICAL 和 ERROR 级别的问题，适合在提交前快速拦截严重代码缺陷。

### Post-commit 异步审查

在 Git post-commit 钩子中调用，对指定提交进行完整审查：

```bash
ai-review check --async --commit <sha>
```

审查结果会写入 Inbox 通知中心，不会阻塞提交流程。

### 手动全量审查

直接运行不带钩子参数，对当前分支变更进行完整审查：

```bash
# 对比当前分支与 main 分支的差异
ai-review check

# 指定基准分支
ai-review check --base develop

# 仅审查指定路径
ai-review check --path src/core/
```

### 选项

| 选项 | 说明 |
| ---- | ---- |
| `--pre-commit` | Pre-commit 模式，快速筛查暂存文件 |
| `--async` | Post-commit 异步模式，需配合 `--commit` 使用 |
| `--commit <sha>` | 指定要审查的提交 SHA |
| `--base <branch>` | 指定基准分支，默认为 `main` |
| `--path <path>` | 仅审查指定路径下的文件 |
| `--no-block` | 发现问题时仍允许提交通过 |
| `--verbose` / `-v` | 输出详细审查过程信息 |
| `--debug` | 输出调试级别日志，用于问题排查 |
| `--open-dashboard` | 审查完成后自动打开 HTML 仪表盘 |

## ai-review inbox

管理审查结果通知，查看和处理代码审查报告。

```bash
# 列出所有通知
ai-review inbox list

# 仅显示未读通知
ai-review inbox list --unread

# 限制显示数量
ai-review inbox list --limit 10

# 显示所有通知（包括已读）
ai-review inbox list --all

# 以 Markdown 格式输出
ai-review inbox list --md
```

### 查看通知详情

```bash
# 查看指定通知的完整内容
ai-review inbox show <notification-id>
```

### 标记通知状态

```bash
# 标记为已读
ai-review inbox read <notification-id>

# 标记为未读
ai-review inbox unread <notification-id>

# 一键标记所有通知为已读
ai-review inbox mark-all-read
```

### 仪表盘视图

```bash
# 在浏览器中打开 HTML 仪表盘
ai-review inbox dashboard
```

### 选项

| 选项 | 说明 |
| ---- | ---- |
| `--unread` | 仅显示未读通知 |
| `--status <status>` | 按状态筛选，可选 `read`、`unread` |
| `--limit <n>` | 限制显示数量 |
| `--all` | 显示所有通知，包括已读 |
| `--md` | 以 Markdown 格式输出结果 |

## ai-review suppress

管理规则抑制列表，用于临时或永久忽略特定审查规则。

```bash
# 抑制指定文件中的某条规则
ai-review suppress src/utils/auth.py hardcode-secret --reason "使用测试专用密钥"

# 抑制文件中的所有规则
ai-review suppress src/mock/data.py --all --reason "测试数据文件"

# 取消抑制
ai-review suppress src/utils/auth.py hardcode-secret --cancel

# 查看当前所有抑制项
ai-review suppress --list
```

### 选项

| 选项 | 说明 |
| ---- | ---- |
| `<file>` | 目标文件路径 |
| `<rule_id>` | 要抑制的规则 ID |
| `--reason <text>` | 抑制原因说明（推荐填写） |
| `--all` | 抑制文件中的所有规则 |
| `--cancel` | 取消已有的抑制项 |
| `--list` | 列出所有当前有效的抑制项 |

:::warning 注意
抑制规则会跳过对应的审查检查，请确保仅在充分了解影响的情况下使用，并填写清晰的 `--reason` 说明原因。
:::

## ai-review status

显示项目中的高风险文件列表，基于记忆系统中的历史审查数据计算风险分数。

```bash
ai-review status
```

输出内容包括：

- 文件路径
- 风险分数（由历史问题的严重程度和重复次数计算）
- 最近一次审查中发现的主要问题

## ai-review config-show

显示当前生效的完整配置，包含所有层级合并后的最终结果。

```bash
ai-review config-show
```

此命令会输出深度合并后的完整配置，方便排查配置问题或确认某个配置项的最终值。

:::tip 使用场景
当你不确定某项配置的实际生效值时，使用 `config-show` 可以快速确认，无需逐层检查多个配置文件。
:::
