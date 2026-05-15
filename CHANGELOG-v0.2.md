# AI Code Review v0.2.0 ~ v0.2.3 变动说明

> 更新日期：2025-05-15
> 安装命令：`pip install --upgrade soloshine-ai-code-review`
> 验证版本：`pip show soloshine-ai-code-review`
> 验证状态：全部通过 ✅

---

## 一、版本总览

| 版本 | 性质 | 核心内容 |
|------|------|---------|
| v0.2.0 | 功能 + 修复 | 智能文件分组、三明治截断、自动 .gitignore |
| v0.2.1 | Bug 修复 | 修复验证报告中 6 个问题（见下文） |
| v0.2.2 | 优化 | Prompt 智能预算分配、max_tokens 提升 |
| v0.2.3 | Bug 修复 | core.hookspath 检测、hook 动态路径、已有 hook 合并 |

---

## 二、逐项变动详情

### 1. 智能文件分组（v0.2.0）

**之前**：所有文件的 diff 合并成一次 LLM 请求，大 diff 导致超时

**现在**：
- 大文件（>200 行）→ 单独一次 LLM 请求
- 小文件 → 合并为一次请求（最多 15 个文件 / 500 行）
- LLM 首次失败后跳过剩余批次，不逐个超时

**影响**：
- 单个大 Vue 文件不再导致超时
- 批量重命名（200+ 文件）可在 1 秒内完成
- Post-commit 使用更高阈值：300 行单独 / 2000 行合并 / 20 个文件

### 2. 三明治截断（v0.2.0）

**之前**：超大 diff 无截断，直接发给 LLM

**现在**：超出限制时保留头部 60% + 尾部 40%，中间用摘要替代（如 `+50 -3`）

### 3. 自动 .gitignore（v0.2.0）

**之前**：需手动添加 `.ai-review/` 到 .gitignore

**现在**：`ai-review init` 自动更新 `.gitignore`：
- 忽略：`memory.json`、`suppressions.json`、`reports/`
- 保留：`rules/` 目录（版本控制，团队共享）

幂等，不会重复添加。

### 4. 超时默认值提升（v0.2.0）

| 模式 | 之前 | 现在 |
|------|------|------|
| balanced | 30s | 60s |
| strict | 60s | 90s |

### 5. 修复 Parser 崩溃（v0.2.1）

**问题**：LLM 返回非 JSON 内容时 `TypeError: ReviewResult.__init__() missing 1 required positional argument: 'highlights'`

**修复**：`parser.py` 文本解析分支补上 `highlights=[]`

### 6. 修复 Git Submodule hooks 安装（v0.2.1）

**问题**：Submodule 中 `.git` 是文件不是目录，`[WinError 3] 系统找不到指定的路径`

**修复**：三种策略依次尝试：
1. `.git` 是目录 → 直接用
2. `.git` 是文件 → 读取 `gitdir:` 内容获取真实路径
3. 以上都失败 → `git rev-parse --git-dir`

### 7. 修复 Hook 脚本 PATH 问题（v0.2.1）

**问题**：Git hook 运行在最小化 shell，`ai-review: command not found`

**修复**：`ai-review init` 时解析 `ai-review` 的完整安装路径，写入 hook 脚本。查找顺序：
1. 当前 Python 的 Scripts 目录
2. `shutil.which("ai-review")`
3. 回退到 `python -m ai_review.cli`

### 8. 支持 `severity: "critical"`（v0.2.1）

**之前**：规则引擎只接受 error / warning / info，写 `critical` 会报错

**现在**：统一支持 critical / error / warning / info 四级
- 规则中 `severity: "critical"` 不会再被拒绝
- pre-commit 的 `rules_filter: ["error"]` 自动匹配 `critical` 规则（critical ≥ error）

### 9. Prompt 智能预算分配（v0.2.2）

**之前**：full 模式 prompt 的规则文本硬截断到 3000 字符，可能从规则中间截断

**现在**：
- 规则按 severity 排序（critical > error > warning > info）
- 超出预算时丢弃低优先级的**完整规则**，而非从中间截断
- 每条规则始终保持完整

**预算分配**：

| 区段 | 字符预算 |
|------|---------|
| 项目结构 (context) | 4000 |
| 审查规范 (rules) | 6000 |
| 历史警告 (warnings) | 1500 |
| 代码变更 (diff) | 15000 |

### 10. max_tokens 可配置（v0.2.1 + v0.2.2）

**之前**：硬编码 4000

**现在**：默认 16000，可在 `.ai-review.yaml` 中配置：

```yaml
llm:
  openai_compatible:
    max_tokens: 32000  # 按需调整
```

### 11. core.hookspath 检测（v0.2.3）

**问题**：`ai-review init` 将 hook 安装到 `.git/hooks/`，但如果项目配置了 `core.hookspath`（如使用 husky、lefthook），Git 只查找 `core.hookspath` 指定的目录，hook 永远不会执行。

**修复**：
- `init` 时检查 `git config core.hookspath`
- 如果设置了 `core.hookspath`，将 hook 安装到该目录而非 `.git/hooks/`
- 输出明确提示安装路径，让用户知道检测到了 `core.hookspath`

### 12. Hook 脚本动态路径查找（v0.2.3）

**之前**：hook 脚本中 `ai-review` 使用安装时的硬编码绝对路径

**现在**：hook 脚本包含三级回退查找：
1. 安装时解析的路径（如果文件仍存在）
2. `command -v ai-review` 动态查找
3. `python -m ai_review.cli` 最终回退

```bash
_ai_review_cmd="C:/Users/.../ai-review.exe"  # 安装时路径
if [ ! -f "$_ai_review_cmd" ]; then
    _ai_review_cmd=$(command -v ai-review 2>/dev/null)
fi
if [ -z "$_ai_review_cmd" ]; then
    _ai_review_cmd="python -m ai_review.cli"
fi
```

### 13. 已有 hook 合并改进（v0.2.3）

**之前**：检测到已有 hook 时直接跳过或静默覆盖

**现在**：
- 已有 hook 不含 ai-review → 追加 ai-review 段落
- 已有 hook 包含 ai-review → 智能替换为更新版本
- 追加时输出提示：`ℹ️  Appended ai-review to existing pre-commit hook`

---

## 三、升级步骤

```bash
# 1. 升级
pip install --upgrade soloshine-ai-code-review

# 2. 确认版本
pip show soloshine-ai-code-review | grep Version

# 3. 清理旧包（如果之前装过 ai-code-reviewer）
pip uninstall ai-code-reviewer -y 2>/dev/null

# 4. 重新初始化（会更新 hooks 脚本，支持 core.hookspath 检测）
cd your-project
ai-review init
```

---

## 四、测试验证清单

### 基础功能

```
[ ] ai-review --help 正常输出
[ ] ai-review config-show 显示正确配置（timeout 应为 60）
[ ] ai-review init 在普通 Git 仓库正常安装 hooks
[ ] .gitignore 中包含 memory.json / suppressions.json / reports/ 条目
[ ] .ai-review/rules/ 未被 gitignore
```

### Submodule 项目

```
[ ] ai-review init 在 submodule 项目中正常安装 hooks
[ ] hooks 安装到 .git/modules/<submodule>/hooks/ 而非报错
```

### Hook 脚本

```
[ ] .git/hooks/pre-commit 内容包含 ai-review 完整路径（非 bare "ai-review"）
[ ] git commit 能正常触发 pre-commit hook
[ ] hook 不再报 "ai-review: command not found"
```

### core.hookspath 检测（v0.2.3 新增）

```
[ ] 设置 core.hookspath 后运行 ai-review init：
    a. 能检测到 core.hookspath 配置
    b. hook 安装到 core.hookspath 指定的目录
    c. 输出提示：Detected core.hookspath=...
    d. git commit 能触发 hook
[ ] 已有 pre-commit hook 的项目中运行 ai-review init：
    a. 检测到已有 hook 并提示
    b. ai-review 段落追加到已有 hook 末尾
    c. 两个 hook 功能均正常
```

### 规则引擎

```
[ ] severity: "critical" 的规则文件正常加载，不报错
[ ] severity: "error" 的 filter 也能匹配 critical 规则
[ ] ai-review check --pre-commit 正常运行
```

### LLM 调用

```
[ ] ai-review check 正常返回审查结果（不超时）
[ ] 非 JSON 返回不再崩溃（测试方法：临时改 prompt 让 LLM 返回纯文本）
[ ] max_tokens 配置生效（在 config-show 中确认值）
```

### 极端场景

```
[ ] 单个大文件（>500 行 Vue）pre-commit 不超时
[ ] 30+ 文件批量提交快速通过
[ ] 批量重命名（100+ 文件）不超时
```
