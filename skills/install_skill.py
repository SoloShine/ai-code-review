#!/usr/bin/env python3
"""
AI Code Review - Skill 安装器

将 ai-review-setup skill 安装到各种 AI coding agent 的规则/指令目录。
支持：Claude Code, Cursor, GitHub Copilot, Windsurf, Cline, OpenCode, Aider

用法：
  python install_skill.py              # 交互式安装
  python install_skill.py --agent claude-code,cursor  # 指定 agent
  python install_skill.py --all        # 安装到所有检测到的 agent
  python install_skill.py --list       # 列出支持的 agent
"""

import argparse
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR / "ai-review-setup"
SKILL_FILE = SKILL_DIR / "SKILL.md"
ADAPTERS_DIR = SKILL_DIR / "adapters"
HOME = Path.home()
CWD = Path.cwd()


def read_file(path):
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def read_skill():
    return read_file(SKILL_FILE)


def read_adapter(agent_id):
    """读取 adapter 文件，如果不存在则从 AGENTS 定义的内联 adapter 获取。"""
    path = ADAPTERS_DIR / f"{agent_id}.yaml"
    if path.exists():
        return read_file(path)
    cfg = AGENTS.get(agent_id, {})
    return cfg.get("inline_adapter", "")


def build_content(agent_id):
    """拼接 adapter 头部 + SKILL.md 内容。"""
    skill = read_skill()
    adapter = read_adapter(agent_id).strip()

    if adapter:
        return adapter + "\n\n" + skill
    return skill


# ── Agent 定义 ──────────────────────────────────────────────
#
# inline_adapter: agent 需要的 frontmatter/头部内容。
# 如果 agent 的 adapter.yaml 文件存在则优先使用文件，否则用内联的。
# 不需要头部的 agent（纯 markdown 追加）设 inline_adapter 为空字符串。

AGENTS = {
    "claude-code": {
        "name": "Claude Code",
        "system_paths": [
            HOME / ".claude" / "skills" / "ai-review-setup" / "SKILL.md",
        ],
        "project_paths": [
            CWD / ".claude" / "skills" / "ai-review-setup" / "SKILL.md",
        ],
        "detect": [HOME / ".claude"],
        "append_mode": False,
        "inline_adapter": (
            "---\n"
            "name: ai-review-setup\n"
            "description: \"配置 AI Code Review 工具到当前项目。安装 ai-review、配置 LLM 后端、"
            "生成审查规则、安装 git hooks。当用户说\\\"配置代码审查\\\"、\\\"安装 ai-review\\\"、"
            "\\\"设置 review\\\" 时触发。\"\n"
            "---\n"
        ),
    },
    "cursor": {
        "name": "Cursor",
        "system_paths": [],
        "project_paths": [
            CWD / ".cursor" / "rules" / "ai-review-setup.mdc",
        ],
        "detect": [HOME / ".cursor"],
        "append_mode": False,
        "inline_adapter": (
            "---\n"
            "description: 配置 AI Code Review - 安装 ai-review、配置 LLM 后端、生成审查规则、安装 git hooks\n"
            "alwaysApply: false\n"
            "globs:\n"
            "  - \"**/*\"\n"
            "---\n"
        ),
    },
    "copilot": {
        "name": "GitHub Copilot",
        "system_paths": [],
        "project_paths": [
            CWD / ".github" / "copilot-instructions.md",
        ],
        "detect": [CWD / ".github"],
        "append_mode": True,
        "append_header": "\n\n## AI Code Review Setup\n\n",
        "inline_adapter": "",
    },
    "windsurf": {
        "name": "Windsurf",
        "system_paths": [
            HOME / ".codeium" / "windsurf" / "memories" / "global_rules.md",
        ],
        "project_paths": [
            CWD / ".windsurf" / "rules" / "ai-review-setup.md",
        ],
        "detect": [HOME / ".codeium"],
        "append_mode": False,
        "inline_adapter": (
            "---\n"
            "trigger: always_on\n"
            "---\n"
        ),
    },
    "cline": {
        "name": "Cline",
        "system_paths": [
            HOME / "Documents" / "Cline" / "Rules" / "ai-review-setup.md",
        ],
        "project_paths": [
            CWD / ".clinerules" / "ai-review-setup.md",
        ],
        "detect": [HOME / "Documents" / "Cline"],
        "append_mode": False,
        "inline_adapter": "",
    },
    "opencode": {
        "name": "OpenCode",
        "system_paths": [
            HOME / ".config" / "opencode" / "commands" / "ai-review-setup.md",
            HOME / ".opencode" / "commands" / "ai-review-setup.md",
        ],
        "project_paths": [
            CWD / ".opencode" / "commands" / "ai-review-setup.md",
        ],
        "detect": [HOME / ".config" / "opencode", HOME / ".opencode"],
        "append_mode": False,
        "inline_adapter": "",
    },
    "aider": {
        "name": "Aider",
        "system_paths": [],
        "project_paths": [
            CWD / "CONVENTIONS.md",
        ],
        "detect": [HOME / ".aider.conf.yml"],
        "append_mode": True,
        "append_header": "\n\n## AI Code Review Setup\n\n",
        "inline_adapter": "",
    },
}


def detect_agents():
    """返回检测到的 agent ID 列表。"""
    found = []
    for agent_id, cfg in AGENTS.items():
        for detect_path in cfg["detect"]:
            if detect_path.exists():
                found.append(agent_id)
                break
    return found


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_to_file(path, content):
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if "AI Code Review Setup" in existing or "ai-review-setup" in existing:
            return False
        path.write_text(existing + content, encoding="utf-8")
        return True
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True


def install_agent(agent_id, level="project"):
    """安装 skill 到指定 agent。level: 'system', 'project', 'both'。"""
    cfg = AGENTS[agent_id]
    content = build_content(agent_id)
    results = []

    paths = []
    if level in ("system", "both"):
        paths.extend(cfg["system_paths"])
    if level in ("project", "both"):
        paths.extend(cfg["project_paths"])

    for target in paths:
        if cfg.get("append_mode"):
            header = cfg.get("append_header", "\n\n")
            ok = append_to_file(target, header + content)
            if ok:
                results.append(("  ✓", str(target)))
            else:
                results.append(("  ·", f"{target} (已存在，跳过)"))
        else:
            write_file(target, content)
            results.append(("  ✓", str(target)))

    return results


def interactive_install():
    """交互式安装流程。"""
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   AI Code Review - Skill 安装器          ║")
    print("╚══════════════════════════════════════════╝")
    print()

    detected = detect_agents()
    if detected:
        print("检测到以下 AI Agent 环境:")
        for aid in detected:
            print(f"  ✓ {AGENTS[aid]['name']}")
    else:
        print("未检测到已安装的 AI Agent 环境（不影响安装）。")

    print()
    print("支持的 AI Agent:")
    agent_ids = list(AGENTS.keys())
    for i, aid in enumerate(agent_ids, 1):
        marker = " ✓" if aid in detected else "  "
        print(f"  [{i}] {AGENTS[aid]['name']}{marker}")
    print("  [a] 全部安装")
    print()

    choice = input("请选择 (如 1,2,3 或 a): ").strip().lower()
    print()

    if choice == "a":
        selected = agent_ids
    else:
        selected = []
        for part in choice.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(agent_ids):
                    selected.append(agent_ids[idx])
            elif part in AGENTS:
                selected.append(part)

    if not selected:
        print("未选择任何 agent，退出。")
        return

    print("安装级别:")
    print("  [1] 项目级（当前项目目录，推荐）")
    print("  [2] 系统级（全局目录，所有项目可用）")
    print("  [3] 两者都安装")
    print()

    level_choice = input("请选择 (默认 1): ").strip()
    level_map = {"1": "project", "2": "system", "3": "both", "": "project"}
    level = level_map.get(level_choice, "project")

    print()
    print(f"正在安装 (级别: {level})...")
    print()

    for aid in selected:
        name = AGENTS[aid]["name"]
        print(f"📦 {name}:")
        results = install_agent(aid, level)
        for icon, path in results:
            print(f"  {icon} {path}")
        print()

    print("✅ 安装完成！")
    print()
    print("下一步：")
    print("  1. 在 AI Agent 中打开你的项目")
    print("  2. 说 '帮我配置代码审查' 或 '安装 ai-review'")
    print("  3. AI 会自动执行完整的安装和配置流程")
    print()


def main():
    parser = argparse.ArgumentParser(description="AI Code Review Skill 安装器")
    parser.add_argument("--list", action="store_true", help="列出支持的 agent")
    parser.add_argument("--agent", type=str, help="指定 agent (逗号分隔，如 claude-code,cursor)")
    parser.add_argument("--all", action="store_true", help="安装到所有 agent")
    parser.add_argument("--level", choices=["system", "project", "both"], default="project",
                        help="安装级别 (默认: project)")
    args = parser.parse_args()

    if args.list:
        print("支持的 AI Agent:")
        detected = detect_agents()
        for aid, cfg in AGENTS.items():
            marker = " ✓ 已检测" if aid in detected else ""
            print(f"  {aid:15s} {cfg['name']}{marker}")
        return

    if args.all:
        selected = list(AGENTS.keys())
    elif args.agent:
        selected = [a.strip() for a in args.agent.split(",")]
    else:
        interactive_install()
        return

    print("正在安装...")
    for aid in selected:
        if aid not in AGENTS:
            print(f"  ✗ 未知 agent: {aid}")
            continue
        name = AGENTS[aid]["name"]
        print(f"📦 {name}:")
        results = install_agent(aid, args.level)
        for icon, path in results:
            print(f"  {icon} {path}")

    print("\n✅ 安装完成！")


if __name__ == "__main__":
    main()
