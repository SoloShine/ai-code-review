---
title: "AI Agent 一键配置"
---

# AI Agent 一键配置

通过 Skill 安装器，让你的 AI coding agent 自动完成 AI Code Review 的全套安装和配置，无需手动操作。

## 支持的 Agent

| Agent | 项目级路径 | 系统级路径 |
|-------|-----------|-----------|
| **Claude Code** | `.claude/skills/ai-review-setup/SKILL.md` | `~/.claude/skills/ai-review-setup/SKILL.md` |
| **Cursor** | `.cursor/rules/ai-review-setup.mdc` | — |
| **GitHub Copilot** | `.github/copilot-instructions.md` | — |
| **Windsurf** | `.windsurf/rules/ai-review-setup.md` | `~/.codeium/windsurf/memories/global_rules.md` |
| **Cline** | `.clinerules/ai-review-setup.md` | `~/Documents/Cline/Rules/ai-review-setup.md` |
| **OpenCode** | `.opencode/commands/ai-review-setup.md` | `~/.config/opencode/commands/ai-review-setup.md` |
| **Aider** | `CONVENTIONS.md` | — |

## 安装步骤

### 1. 下载安装器

```bash
git clone https://github.com/SoloShine/ai-code-review.git
```

### 2. 运行安装器

```bash
# 交互式安装（推荐）
python ai-code-review/skills/install_skill.py
```

安装器会自动检测你已安装的 AI agent，并让你选择安装目标。

你也可以使用命令行参数：

```bash
# 安装到指定 agent
python ai-code-review/skills/install_skill.py --agent claude-code,cursor

# 安装到所有 agent
python ai-code-review/skills/install_skill.py --all

# 列出支持的 agent
python ai-code-review/skills/install_skill.py --list

# 指定安装级别（项目级 / 系统级 / 两者）
python ai-code-review/skills/install_skill.py --agent claude-code --level system
python ai-code-review/skills/install_skill.py --agent claude-code --level both
```

### 3. 触发自动配置

安装完成后，在你的 AI agent 中打开任意项目，然后说：

- "帮我配置代码审查"
- "安装 ai-review"
- "设置 pre-commit review"

AI agent 会自动完成以下操作：

1. **环境检查** — 确认 Python 版本和 Git 仓库
2. **安装 ai-review** — 通过 pip 安装 CLI 工具
3. **项目初始化** — 创建配置文件和 Git hooks
4. **配置 LLM 后端** — 根据你的选择生成 `.ai-review.yaml`
5. **生成审查规则** — 扫描项目技术栈，自动匹配规则
6. **验证安装** — 确认所有组件正常工作

## 工作原理

```
SKILL.md（核心指令）
    + adapters/<agent>.yaml（格式适配）
    ──→ 安装器拼接 ──→ 写入目标 agent 目录
```

- `SKILL.md`：通用的 skill 内容，指导 AI agent 完成 ai-review 的安装和配置
- `adapters/`：每个 AI agent 的格式适配（frontmatter、目录规范等）
- `install_skill.py`：将 skill 安装到各 agent 的正确位置

## 注意事项

- 安装器是**幂等**的 — 已有内容不会重复追加
- 支持 Windows、macOS、Linux 跨平台
- Skill 安装后，每次在项目中使用 AI agent 时都可以触发配置
- LLM 故障时自动放行，不会阻塞你的正常开发流程
