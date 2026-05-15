# AI Code Review - 项目配置指南

本 skill 指导你在一个项目中完成 AI Code Review 工具的安装和配置。

## 何时使用

当用户说以下任何一种时触发：
- "配置代码审查" / "设置代码审查"
- "安装 ai-review" / "初始化 ai-review"
- "设置 pre-commit review" / "添加 AI 审查"
- "帮我配置 ai-code-review"

## 执行步骤

### Step 1: 环境检查

检查以下条件是否满足：

1. **Python 版本** — 需要 >= 3.10
   ```bash
   python --version
   ```
   如果版本过低，告知用户升级 Python。

2. **Git 仓库** — 当前目录必须是 Git 仓库
   ```bash
   git rev-parse --git-dir
   ```
   如果不是，询问用户是否要 `git init`。

3. **ai-review 是否已安装**
   ```bash
   ai-review --help
   ```

### Step 2: 安装 ai-review（如未安装）

从 PyPI 安装：
```bash
pip install soloshine-ai-code-review
```

验证安装：
```bash
ai-review --help
```

如果安装失败，检查：
- Python 版本是否 >= 3.10
- pip 是否可用
- 网络连接是否正常

如果用户系统上有旧包 `ai-code-reviewer`，先卸载：
```bash
pip uninstall ai-code-reviewer -y
```

### Step 3: 项目初始化

运行初始化命令：
```bash
ai-review init
```

该命令会自动：
- 创建 `.ai-review.yaml` 配置文件
- 创建 `.ai-review/rules/` 目录（含示例规则）
- 安装 Git pre-commit 和 post-commit 钩子（支持 submodule/worktree）
- 更新 `.gitignore`：忽略 memory.json / suppressions.json / reports/，保留 rules/ 供版本控制

确认 hooks 安装成功（submodule 项目中路径可能在 `.git/modules/` 下）：
```bash
ai-review init  # 如果显示路径包含 modules，说明正确识别了 submodule
```

### Step 4: 配置 LLM 后端

询问用户选择 LLM 后端，然后写入 `.ai-review.yaml`。

**选项：**

| 后端 | 适用场景 | 需要 API Key |
|------|---------|-------------|
| 智谱 GLM (推荐国内用户) | 国内访问快，中文优化 | ZHIPU_API_KEY |
| DeepSeek | 代码能力强 | DEEPSEEK_API_KEY |
| 通义千问 | 阿里云生态 | DASHSCOPE_API_KEY |
| Ollama | 本地部署，无网络要求 | 无 |

根据用户选择，生成对应的 `.ai-review.yaml`：

**智谱 GLM：**
```yaml
mode: "balanced"
llm:
  backend: "openai_compatible"
  openai_compatible:
    base_url: "https://open.bigmodel.cn/api/coding/paas/v4"
    api_key_env: "ZHIPU_API_KEY"
    model: "glm-5-turbo"
    timeout: 60
    max_tokens: 16000
hooks:
  pre_commit:
    timeout: 60
    block_on: ["CRITICAL", "ERROR"]
  post_commit:
    enabled: true
memory:
  enabled: true
  risk_threshold: 5
dashboard:
  auto_open: true
exclude:
  - "*.lock"
  - "*.min.js"
  - "*.min.css"
  - "node_modules/"
  - "__pycache__/"
  - "dist/"
```

**DeepSeek：**
```yaml
mode: "balanced"
llm:
  backend: "openai_compatible"
  openai_compatible:
    base_url: "https://api.deepseek.com/v1"
    api_key_env: "DEEPSEEK_API_KEY"
    model: "deepseek-chat"
    timeout: 60
    max_tokens: 16000
```

**Ollama（本地）：**
先确认 Ollama 已安装且模型已拉取：
```bash
ollama list
# 如果没有模型，拉取推荐模型：
ollama pull qwen2.5-coder:7b
```

```yaml
mode: "balanced"
llm:
  backend: "ollama"
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5-coder:7b"
    timeout: 120
```

### Step 5: 设置 API Key

如果选择了需要 API Key 的后端，帮助用户设置环境变量。

**Linux/macOS：**
```bash
# 追加到 shell 配置文件
echo 'export ZHIPU_API_KEY="your-key-here"' >> ~/.bashrc  # 或 ~/.zshrc
source ~/.bashrc
```

**Windows PowerShell：**
```powershell
# 永久设置（用户级别）
[Environment]::SetEnvironmentVariable("ZHIPU_API_KEY", "your-key-here", "User")
```

提醒用户：
- API Key 设置后需重启终端才生效
- 不要把 API Key 写入代码或提交到 Git

### Step 6: 生成项目审查规则

扫描项目技术栈，自动生成匹配的规则文件。

**检测逻辑：**

1. 检查 `package.json` → 前端项目
2. 检查 `requirements.txt` / `pyproject.toml` → Python 项目
3. 检查 `pom.xml` / `build.gradle` → Java 项目
4. 检查 `*.go` / `go.mod` → Go 项目
5. 检查文件扩展名分布 → 综合判断

**生成规则：**

在 `.ai-review/rules/` 下生成对应的 YAML 文件。severity 支持四级：`critical` / `error` / `warning` / `info`。

**前端规则** (`frontend.yaml`)：
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

  - id: "promise-catch"
    title: "Promise 必须处理错误"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "所有 Promise 链必须包含 .catch() 或使用 try/catch 包裹 async/await。"

  - id: "no-settimeout"
    title: "禁止使用 setTimeout"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "禁止使用 setTimeout 处理时序性问题，应使用 Promise/nextTick 等可靠机制。"

  - id: "no-hardcoded-secrets"
    title: "禁止硬编码密钥"
    severity: "critical"
    enabled: true
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: "禁止在代码中硬编码 API Key、密码等敏感信息，应使用环境变量。"
```

**Python 规则** (`python.yaml`)：
```yaml
name: "Python Backend Rules"
description: "Python code review rules"
rules:
  - id: "no-eval"
    title: "禁止使用 eval"
    severity: "critical"
    enabled: true
    applies_to:
      extensions: [".py"]
    description: "禁止使用 eval，存在严重的代码注入安全风险。"

  - id: "sql-injection"
    title: "防止 SQL 注入"
    severity: "critical"
    enabled: true
    applies_to:
      extensions: [".py"]
    description: "禁止拼接 SQL 语句，必须使用参数化查询。"

  - id: "no-hardcoded-secrets"
    title: "禁止硬编码密钥"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".py"]
    description: "禁止在代码中硬编码 API Key、密码等敏感信息，应使用环境变量。"

  - id: "no-bare-except"
    title: "禁止裸 except"
    severity: "warning"
    enabled: true
    applies_to:
      extensions: [".py"]
    description: "禁止使用 bare except:，应明确捕获具体异常类型。"
```

如果是全栈项目，两种规则都生成。

### Step 7: 验证安装

1. 检查配置：
```bash
ai-review config-show
```

2. 检查规则加载：
```bash
ai-review check --verbose
```

3. 确认 Git Hooks 已安装：
```bash
# 普通项目
ls .git/hooks/pre-commit
# submodule 项目（路径可能不同）
git rev-parse --git-dir
# 查看该目录下的 hooks/
```

4. 向用户报告安装结果：
```
✅ AI Code Review 配置完成！

已安装组件：
  • ai-review CLI
  • Git pre-commit hook (快速筛查)
  • Git post-commit hook (异步全量审查)
  • 审查规则: X 条 (前端/后端)
  • LLM 后端: [用户选择的后端]
  • .gitignore 已更新 (生成文件忽略，rules/ 保留版本控制)

下一步：
  1. 正常提交代码即可触发审查
  2. 运行 ai-review inbox 查看审查报告
  3. 运行 ai-review inbox dashboard 打开 HTML 仪表盘
  4. 运行 ai-review suppress <file> <rule> 抑制已知问题
```

## 重要注意事项

- **LLM 故障不阻塞提交**：ai-review 在 LLM 不可用时自动放行，不会影响正常工作流
- **首次提交**可能较慢（LLM 冷启动），后续会更快
- **规则可以随时修改**：编辑 `.ai-review/rules/` 下的 YAML 文件，rules/ 目录会被版本控制
- **大文件自动处理**：超过 200 行的文件单独审查，小文件合并审查，批量重命名不会超时
- **max_tokens 可调**：如果审查结果被截断，在配置中增大 `max_tokens`（默认 16000）
- **severity 四级**：规则支持 critical / error / warning / info，critical 最严重
