# AI Code Review - Skills

AI Code Review 的 skill 安装包，让你的 AI coding agent 自动帮你配置代码审查工具。

## 快速安装

```bash
# 克隆或下载本项目后，运行安装器
python skills/install_skill.py
```

安装器会交互式引导你选择要安装到哪些 AI agent。

## 支持的 AI Agent

| Agent | 项目级路径 | 系统级路径 |
|-------|-----------|-----------|
| **Claude Code** | `.claude/skills/ai-review-setup/SKILL.md` | `~/.claude/skills/ai-review-setup/SKILL.md` |
| **Cursor** | `.cursor/rules/ai-review-setup.mdc` | — |
| **GitHub Copilot** | `.github/copilot-instructions.md` | — |
| **Windsurf** | `.windsurf/rules/ai-review-setup.md` | `~/.codeium/windsurf/memories/global_rules.md` |
| **Cline** | `.clinerules/ai-review-setup.md` | `~/Documents/Cline/Rules/ai-review-setup.md` |
| **OpenCode** | `.opencode/commands/ai-review-setup.md` | `~/.config/opencode/commands/ai-review-setup.md` |
| **Aider** | `CONVENTIONS.md` | — |

## 命令行用法

```bash
# 交互式安装（推荐）
python skills/install_skill.py

# 安装到指定 agent
python skills/install_skill.py --agent claude-code,cursor

# 安装到所有 agent
python skills/install_skill.py --all

# 列出支持的 agent
python skills/install_skill.py --list

# 指定安装级别
python skills/install_skill.py --agent claude-code --level system
python skills/install_skill.py --agent claude-code --level both
```

## 使用方法

安装完成后，在你的 AI agent 中打开任意项目，然后说：

- "帮我配置代码审查"
- "安装 ai-review"
- "设置 pre-commit review"

AI agent 会自动执行完整的安装和配置流程。

## 工作原理

```
SKILL.md（核心指令）
    + adapters/<agent>.yaml（格式适配）
    ──→ 安装器拼接 ──→ 写入目标 agent 目录
```

- `SKILL.md`：通用的 skill 内容，指导 AI agent 完成 ai-review 的安装和配置
- `adapters/`：每个 AI agent 的格式适配（frontmatter、目录规范等）
- `install_skill.py`：将 skill 安装到各 agent 的正确位置

## 目录结构

```
skills/
├── ai-review-setup/
│   ├── SKILL.md                  # 核心 skill 内容
│   └── adapters/                 # 各 agent 的格式适配
│       ├── claude-code.yaml
│       ├── cursor.yaml
│       ├── copilot.yaml
│       ├── windsurf.yaml
│       ├── cline.yaml
│       ├── opencode.yaml
│       └── aider.yaml
├── install_skill.py              # 交互式安装器
└── README.md                     # 本文件
```
