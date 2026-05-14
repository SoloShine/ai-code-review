---
title: "常见问题"
---

# 常见问题

## 提交时没有触发审查？

**现象**：执行 `git commit` 后没有看到 AI 审查的输出。

**排查步骤**：

1. 检查 hooks 是否已安装：

```bash
ls .git/hooks/pre-commit .git/hooks/post-commit
```

2. 如果文件不存在，重新安装：

```bash
ai-review init
```

3. 检查配置文件中的 hooks 是否启用：

```yaml
# ai-review.yml
hooks:
  pre_commit:
    enabled: true
  post_commit:
    enabled: true
```

4. 确认 hook 文件有执行权限（Linux/macOS）：

```bash
chmod +x .git/hooks/pre-commit .git/hooks/post-commit
```

---

## 审查超时怎么办？

**现象**：Pre-commit 阶段报超时错误，或审查耗时过长。

**解决方案**：

在配置文件中增加超时时间：

```yaml
# ai-review.yml
hooks:
  pre_commit:
    timeout: 60                 # 默认 30 秒，增加到 60 秒
llm:
  timeout: 60                   # LLM 请求超时
```

::: tip
如果使用 Ollama 本地模型，可以尝试换用参数量更小的模型（如 `qwen2.5-coder:7b`）来提升响应速度。
:::

---

## 如何临时跳过审查？

有以下几种方式可以临时跳过代码审查：

**方式一：使用 `--no-verify`**

```bash
git commit --no-verify -m "紧急热修复"
```

**方式二：使用环境变量**

在配置中设置 `bypass_env_vars`：

```yaml
hooks:
  bypass_env_vars:
    - SKIP_AI_REVIEW
```

然后通过环境变量跳过：

```bash
SKIP_AI_REVIEW=1 git commit -m "WIP"
```

::: warning
`--no-verify` 会跳过所有 Git hooks（包括非 AI Review 的 hooks），建议优先使用环境变量方式。
:::

---

## 报告中 rule_id 是中文，抑制不生效？

**现象**：在报告中看到 `rule_id: "空指针风险"`，但配置 suppress 后没有效果。

**原因**：AI Code Review 的 rule_id 由 LLM 生成，可能存在措辞差异（如 `"空指针风险"` vs `"空指针检测"`）。

**解决方案**：系统支持**模糊匹配**，你可以使用部分关键词进行匹配：

```yaml
suppress:
  - rule_id: "空指针"           # 会匹配所有包含"空指针"的 rule_id
    files: ["src/legacy/**"]
  - rule_id: "*"                # 通配符，匹配所有规则
    files: ["vendor/**"]
```

---

## 支持 GitLab / Bitbucket 吗？

**支持。** AI Code Review 基于标准 Git hooks 工作，与代码托管平台无关。只要项目是一个 Git 仓库，无论是在 GitHub、GitLab、Bitbucket 还是其他平台，都可以正常使用。

需要注意的是，报告通知目前仅支持桌面通知，不支持直接发送到 GitLab / Bitbucket 的 MR 评论。

---

## LLM 故障怎么办？

**设计原则**：AI Code Review **永远不会因为 LLM 故障而阻塞提交**。

- **Pre-commit 阶段**：如果 LLM 服务不可用或请求失败，hook 会自动放行（auto-pass），提交正常完成
- **Post-commit 阶段**：后台审查失败会记录错误日志，不影响任何 Git 操作

相关日志存储在 `.ai-review/logs/` 目录下，可以查看失败原因。

---

## Windows 通知不显示？

**现象**：代码审查完成但没有弹出桌面通知。

**解决方案**：

Windows 桌面通知依赖 PowerShell 的 `BurntToast` 模块，安装方法：

```powershell
Install-Module -Name BurntToast -Force -Scope CurrentUser
```

安装完成后验证：

```powershell
# 测试通知
New-BurntToastNotification -Text "测试", "通知功能正常"
```

如果安装后仍无法显示，检查以下设置：

1. Windows 系统通知权限是否开启（设置 -> 系统 -> 通知）
2. PowerShell 执行策略是否允许运行脚本

---

## 报告存在哪里？

所有审查报告存储在项目目录下的 `.ai-review/reports/` 中：

```
.ai-review/
  reports/
    2024-01-15_abc1234.json      # 按日期 + commit hash 命名
    2024-01-15_def5678.json
    ...
  memory.json                     # 记忆系统数据
  logs/                           # 运行日志
```

**建议将 `.ai-review/` 添加到 `.gitignore`**：

```bash
echo ".ai-review/" >> .gitignore
```

::: info
`ai-review init` 命令会自动将 `.ai-review/` 添加到 `.gitignore`（如果尚未添加）。
:::
