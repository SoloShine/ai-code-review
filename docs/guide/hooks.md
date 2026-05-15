---
title: "Git Hooks"
---

# Git Hooks

## 工作流程

AI Code Review 通过 Git Hooks 在提交过程的不同阶段自动触发代码审查：

```
git commit
    |
    v
[pre-commit hook]
    |
    v
FastScreener (快速扫描)
    |
    +---> PASS -----> 提交成功
    |                     |
    |                     v
    |              [post-commit hook]
    |                     |
    |                     v
    +---> BLOCK ---> 提交被拒绝    异步完整审查 (Full Review)
                          |                     |
                          v                     v
                    修复后重新提交         生成报告 + 发送通知
```

## Pre-commit Hook

Pre-commit hook 在 `git commit` 执行前触发，负责快速扫描暂存区的代码变更。

**关键特性：**

- **超时时间**：60 秒（balanced 模式），超时自动放行
- **阻断规则**：仅在发现 `CRITICAL` 或 `ERROR` 级别问题时阻止提交
- **智能分组**：大文件（>200 行）单独审查，小文件合并为单次 LLM 请求（最多 15 文件 / 500 行）
- **容错机制**：LLM 服务不可用时自动放行（auto-pass），首次失败后跳过剩余批次，不会逐个超时

```yaml
# ai-review.yml
hooks:
  pre_commit:
    enabled: true
    timeout: 60                 # 超时时间（秒）
    block_on:                   # 阻断级别
      - CRITICAL
      - ERROR
```

## Post-commit Hook

Post-commit hook 在提交成功后触发，执行完整的深度代码审查。

**关键特性：**

- **异步执行**：通过 `nohup` 在后台运行，不阻塞 Git 操作
- **完整审查**：使用 Full Prompt 进行深度分析
- **自动通知**：审查完成后自动发送桌面通知

```yaml
# ai-review.yml
hooks:
  post_commit:
    enabled: true
    async: true                 # 异步执行
    notify: true                # 审查完成后发送通知
```

::: info
Post-commit hook 不会影响 `git commit` 的执行速度，所有审查工作都在后台完成。
:::

## 安装 Hooks

在项目根目录运行以下命令安装 Git Hooks：

```bash
ai-review init
```

该命令会自动完成以下操作：

1. 检查项目是否为 Git 仓库
2. 创建 `.ai-review/` 目录及配置文件
3. 安装 `pre-commit` 和 `post-commit` hook 脚本到 `.git/hooks/`

::: warning
如果你之前已有自定义的 `pre-commit` 或 `post-commit` hook，`ai-review init` 会提示你是否覆盖。建议先备份原有 hook 文件。
:::

## 验证安装

安装完成后，检查 hook 文件是否已正确创建：

```bash
# 检查 hook 文件是否存在
ls -la .git/hooks/pre-commit .git/hooks/post-commit

# 输出应类似：
# -rwxr-xr-x  1 user  staff  ...  .git/hooks/pre-commit
# -rwxr-xr-x  1 user  staff  ...  .git/hooks/post-commit
```

你也可以手动测试 hook 是否正常工作：

```bash
# 干跑测试（不实际执行审查）
ai-review init --dry-run

# 触发一次测试审查
echo "test" >> test.txt && git add test.txt && git commit -m "test: hook test"
```

## 跳过审查

在某些场景下你可能需要临时跳过代码审查：

### 使用 --no-verify

```bash
git commit --no-verify -m "紧急修复：生产环境热修复"
```

### 配置环境变量跳过

在配置文件中设置 `bypass_env_vars`，当指定的环境变量存在时自动跳过审查：

```yaml
# ai-review.yml
hooks:
  bypass_env_vars:
    - CI                        # CI/CD 环境跳过
    - SKIP_AI_REVIEW            # 手动跳过标记
```

```bash
# 临时跳过
SKIP_AI_REVIEW=1 git commit -m "WIP: 临时保存"
```

::: warning
**不建议长期使用 `--no-verify`**。如果某些文件或规则需要排除，请使用 `suppress`（抑制）功能进行精细控制：

```yaml
# ai-review.yml
suppress:
  - rule_id: "naming-convention"
    files: ["legacy/**/*.py"]
  - rule_id: "*"
    files: ["vendor/**"]
```
:::
