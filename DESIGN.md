# AI Code Review 工具 — 技术方案设计

> 目标：零额外费用，支持自定义 LLM（OpenAI 兼容 API + Ollama 本地模型），支持 pre-commit 拦截、主动触发、上下文检索。

---

## 一、需求分析

| 需求 | 说明 |
|------|------|
| Pre-commit 拦截 | git commit 前自动触发审查，严重问题阻断提交 |
| 主动触发 | 开发者随时可通过 CLI 命令手动审查 |
| 上下文检索 | 审查时理解代码库结构、依赖关系、相关文件，而非仅看 diff |
| 自定义 LLM | 同时支持 OpenAI 兼容 API（Deepseek、通义千问等）和 Ollama 本地模型 |
| 零费用 | 全部使用开源组件和已有 API/本地模型，不依赖任何付费 SaaS |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     触发层 (Trigger)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ pre-commit   │  │ CLI 手动触发  │  │ CI/CD 集成    │  │
│  │ (git hook)   │  │ review diff  │  │ (可扩展)      │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         └──────────────────┼──────────────────┘          │
│                            ▼                             │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              核心引擎 (Python)                        │ │
│  │                                                      │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │ │
│  │  │ Diff 采集器  │  │ 上下文引擎  │  │ Prompt 组装  │ │ │
│  │  │ git diff    │  │ Context     │  │ Builder     │ │ │
│  │  │ --cached    │  │ Engine      │  │             │ │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │ │
│  │         └──────────────────┼─────────────────┘       │ │
│  │                            ▼                         │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │           LLM 抽象层 (LLM Provider)              │ │ │
│  │  │  ┌──────────────┐    ┌──────────────────────┐   │ │ │
│  │  │  │ Ollama 本地   │    │ OpenAI 兼容 API      │   │ │ │
│  │  │  │ localhost     │    │ Deepseek/Qwen/...    │   │ │ │
│  │  │  └──────────────┘    └──────────────────────┘   │ │ │
│  │  └────────────────────────┬────────────────────────┘ │ │
│  │                           ▼                          │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │           结果解析 & 决策引擎                      │ │ │
│  │  │  PASS / WARN / BLOCK → 退出码 + 报告             │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 三、核心模块设计

### 3.1 LLM 抽象层

统一接口，屏蔽不同 LLM 后端的差异：

```python
# 配置文件 ~/.ai-review/config.yaml
llm:
  # 使用的后端: "ollama" 或 "openai_compatible"
  backend: "ollama"
  
  # Ollama 配置
  ollama:
    base_url: "http://localhost:11434"
    model: "deepseek-coder-v2"
    timeout: 120
  
  # OpenAI 兼容 API 配置（通用于 Deepseek、通义千问、硅基流动等）
  openai_compatible:
    base_url: "https://api.deepseek.com/v1"  # 或其他兼容端点
    api_key: "${DEEPSEEK_API_KEY}"            # 从环境变量读取
    model: "deepseek-chat"
    timeout: 60
```

```python
# 抽象接口
class LLMProvider(ABC):
    @abstractmethod
    def review(self, prompt: str) -> str: ...

class OllamaProvider(LLMProvider): ...
class OpenAICompatibleProvider(LLMProvider): ...
```

**支持的模型后端：**
- Ollama 本地：Deepseek-Coder、Qwen2.5-Coder、Llama3、CodeLlama 等
- OpenAI 兼容 API：Deepseek、通义千问、硅基流动、零一万物、本地 vLLM 等

### 3.2 上下文引擎

#### 设计思路：从"分析器"到"采集器 + 提醒器"

最初设计的思路是自建 AST 分析和依赖图，但这条路有两个根本问题：

1. **通用性差**：不同项目类型分析逻辑差异巨大。Vue 的组件注册（SFC + components 选项）、.NET 的 using + namespace + .csproj 引用、纯 HTML 的 `<script src>` — 要做通用的 import 解析，要么浅到没意义，要么每种语言写一套适配器
2. **重复造轮子**：用户已经在用 AI agent 编程，agent 本身就能做深度上下文分析，再自建一套是浪费

所以上下文引擎的核心定位不是"我帮你分析上下文"，而是**"确保该有的上下文不会漏"**。具体来说：工具负责自动采集通用信息，用户通过配置定义"审查特定文件时需要什么额外上下文"，agent 用户可选地做深度分析。

#### 三层上下文

```
┌──────────────────────────────────────────────────────┐
│ Layer 1: 自动采集（零配置，所有项目通用）                │
│                                                       │
│  · 项目文件树（精简版，排除 node_modules 等）            │
│  · git log：与变更文件相关的最近 5 条 commit             │
│  · diff stats：本次变更的文件统计                        │
│  · 变更文件的同目录/父目录/子目录文件列表                 │
│                                                       │
│  实现：纯 git 命令 + 文件系统遍历，无语言依赖             │
├──────────────────────────────────────────────────────┤
│ Layer 2: 配置驱动的上下文模板（用户定义）                 │
│                                                       │
│  用户在配置中声明"审查某类文件时需要附带哪些文件"          │
│  工具自动读取并注入 prompt                               │
│  适用于 Vue / .NET / 纯 HTML 等任何项目类型              │
│                                                       │
├──────────────────────────────────────────────────────┤
│ Layer 3: Agent 协作提示（可选）                          │
│                                                       │
│  检测到 agent 环境时，输出上下文分析建议                  │
│  引导用户用 agent 做深度分析                             │
│  不依赖 agent 也能正常工作                               │
└──────────────────────────────────────────────────────┘
```

#### Layer 1：自动采集

```python
class AutoContextCollector:
    """通用上下文自动采集，零配置，无语言依赖"""
    
    def collect(self, changed_files: list[str]) -> AutoContext:
        return AutoContext(
            # 项目文件树（精简版，只到 2 层深度）
            file_tree=self._get_file_tree(depth=2),
            
            # 与变更文件相关的 git log
            git_log=self._get_related_commits(changed_files, limit=5),
            
            # 本次变更统计
            diff_stats=self._get_diff_stats(changed_files),
            
            # 变更文件的周边文件（同目录 + 父目录 + 子目录）
            nearby_files=self._get_nearby_files(changed_files),
        )
    
    def _get_file_tree(self, depth=2) -> str:
        """生成精简的项目文件树"""
        # 排除 node_modules, .git, bin, obj, dist 等
        exclude = ["node_modules", ".git", "bin", "obj", "dist", "build", ".vs"]
        result = subprocess.run(
            ["find", ".", "-maxdepth", str(depth), "-not", "-path", "*/.*"],
            capture_output=True, text=True
        )
        return self._filter_tree(result.stdout, exclude)
    
    def _get_related_commits(self, files, limit=5) -> str:
        """获取与变更文件相关的最近提交"""
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--oneline", "--"] + files,
            capture_output=True, text=True
        )
        return result.stdout
    
    def _get_diff_stats(self, files) -> str:
        """变更统计"""
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat", "--"] + files,
            capture_output=True, text=True
        )
        return result.stdout
    
    def _get_nearby_files(self, changed_files) -> list[str]:
        """收集变更文件周围的文件"""
        nearby = set()
        for f in changed_files:
            parent = str(Path(f).parent)
            # 同目录文件
            for sibling in Path(parent).glob("*"):
                if sibling.is_file() and str(sibling) != f:
                    nearby.add(str(sibling))
        return sorted(nearby)[:20]  # 限制数量
```

#### Layer 2：优先级驱动的渐进式上下文采集

核心问题：用户配置了 `include_patterns: ["src/api/**/*.js"]`，展开后可能 50 个文件。一个 2 行的 CSS 改动和一个新建组件不应该注入同等量级的上下文。

解决方案：**给上下文源分优先级，按 diff 相关性决定是否引入、引入多少**。

##### 配置格式

```yaml
# .ai-review.yaml

context:
  # 自适应 token 预算（上下文部分）
  # 不是固定值，而是根据 diff 规模自动调节（见下方 3.2.1 节）
  budget:
    default: 4000       # 小 diff（<200 行变更）时的上下文预算
    medium: 8000        # 中等 diff（200-800 行）
    large: 12000        # 大 diff（800-2000 行）
    max: 16000          # 上限

  # Layer 1 自动采集（默认开启，不走模板）
  auto:
    file_tree: true
    git_log: true
    diff_stats: true
    nearby_files: true

  # Layer 2 上下文源：按优先级分桶，渐进填充
  sources:
    # ─── 优先级 P0：核心骨架，优先引入 ───
    # 只要变更文件命中 match，这些文件就最先进 prompt
    # 典型用途：路由配置、状态管理入口、项目配置
    - priority: 0
      match:
        extensions: [".vue"]
      context_files:                    # 精确文件，一定会引入（受总预算限制）
        - path: "src/router/index.js"
          max_lines: 100                # 单文件行数上限，超出截断
        - path: "src/store/index.js"
          max_lines: 100

    - priority: 0
      match:
        extensions: [".cs"]
      context_files:
        - path: "Program.cs"
          max_lines: 80
        - path: "appsettings.json"

    # ─── 优先级 P1：相关模块，按 diff 相关性引入 ───
    # 不是全部引入，而是只引入 diff 中实际引用到的文件
    # 典型用途：API 层、Service 层、公共组件
    - priority: 1
      match:
        extensions: [".vue"]
      scan_patterns:                    # 扫描这些路径下的文件
        - "src/api/**/*.js"
        - "src/components/**/index.vue"
      relevance: "diff_ref"             # 按需模式：只在 diff 中引用了才引入
      max_files: 5                      # 最多引入几个文件

    - priority: 1
      match:
        extensions: [".cs"]
      scan_patterns:
        - "**/Services/*.cs"
      relevance: "diff_ref"
      max_files: 3

    # ─── 优先级 P2：补充上下文，预算有剩余才引入 ───
    # 典型用途：README、项目约定、类型定义
    - priority: 2
      match:
        extensions: ["*"]               # 通用，所有文件类型
      context_files:
        - path: "CLAUDE.md"
          max_lines: 50
        - path: ".cursorrules"
          max_lines: 50
        - path: "README.md"
          max_lines: 30

    # 排除：某些文件不需要额外上下文
    - match:
        paths: ["config/**", "*.config.js", "*.lock"]
      context_files: []
      scan_patterns: []
```

##### 采集流程

```
输入：changed_files + diff_content
                      │
                      ▼
              ┌───────────────┐
              │ 匹配 sources  │  按文件类型/路径筛选出命中的 source 规则
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ 按 priority   │  P0 → P1 → P2 逐级填充
              │ 渐进填充       │
              └───────┬───────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    ┌─────────┐  ┌──────────┐  ┌──────────┐
    │ P0: 全量 │  │ P1: 按需  │  │ P2: 补充  │
    │ 引入     │  │ 引入      │  │ 剩余预算  │
    │          │  │          │  │ 才引入    │
    │ 直接读取  │  │ 分析 diff │  │          │
    │ context_ │  │ 中引用的   │  │ 按优先级  │
    │ files    │  │ 文件路径   │  │ 依次塞入  │
    └─────────┘  └──────────┘  └──────────┘
         │            │            │
         └────────────┼────────────┘
                      ▼
              ┌───────────────┐
              │ Token 预算    │  总量不超过 budget (默认 4000 tokens)
              │ 控制          │  超出则截断或跳过低优先级
              └───────┬───────┘
                      │
                      ▼
              最终注入 prompt 的上下文
```

##### 核心实现：diff 相关性过滤

P1 级别的 `relevance: "diff_ref"` 是关键——它不是盲目展开 glob，而是分析 diff 内容，只引入 diff 中实际引用到的文件。

```python
class ProgressiveContextCollector:
    """渐进式上下文采集器"""
    
    def collect(self, changed_files: list[str], diff: str,
                sources: list[ContextSource], budget: int = 4000) -> dict[str, str]:
        
        # 1. 筛选出命中的 source 规则
        matched = [s for s in sources if self._any_matches(changed_files, s.match)]
        
        # 2. 按 priority 分桶
        buckets: dict[int, list[ContextSource]] = defaultdict(list)
        for s in matched:
            buckets[s.priority].append(s)
        
        # 3. 渐进填充
        result = {}
        remaining = budget
        
        # P0：核心骨架，全量引入（受单文件 max_lines 和总预算限制）
        for source in buckets.get(0, []):
            for cf in source.context_files:
                content = self._read_truncated(cf.path, cf.max_lines)
                tokens = self._estimate_tokens(content)
                if tokens <= remaining:
                    result[cf.path] = content
                    remaining -= tokens
        
        # P1：相关模块，按 diff 引用引入
        for source in buckets.get(1, []):
            # 扫描 diff 中出现的文件路径/模块名
            diff_refs = self._extract_diff_references(diff)
            candidates = self._expand_patterns(source.scan_patterns)
            # 只保留 diff 中实际引用到的文件
            relevant = [f for f in candidates
                        if self._is_referenced_in_diff(f, diff_refs)]
            relevant = relevant[:source.max_files]
            for f in relevant:
                if remaining <= 0:
                    break
                content = Path(f).read_text(errors="ignore")
                tokens = self._estimate_tokens(content)
                if tokens <= remaining:
                    result[f] = content
                    remaining -= tokens
        
        # P2：补充上下文，剩余预算有空间才引入
        if remaining > 200:  # 至少留 200 token 给 P2
            for source in buckets.get(2, []):
                for cf in source.context_files:
                    content = self._read_truncated(cf.path, cf.max_lines)
                    tokens = self._estimate_tokens(content)
                    if tokens <= remaining:
                        result[cf.path] = content
                        remaining -= tokens
        
        return result
    
    def _extract_diff_references(self, diff: str) -> set[str]:
        """从 diff 中提取文件引用和模块名（通用，无语言依赖）"""
        refs = set()
        # 匹配 import/require/using 等语句中的路径
        patterns = [
            r'from\s+[\'"]([^\'"]+)[\'"]',        # import x from '...'
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]', # require('...')
            r'using\s+[\w.]+',                      # using X.Y.Z
            r'<script\s+src=[\'"]([^\'"]+)[\'"]',   # <script src="...">
        ]
        for p in patterns:
            for m in re.finditer(p, diff):
                refs.add(m.group(1) if m.lastindex else m.group(0))
        return refs
    
    def _is_referenced_in_diff(self, file_path: str, diff_refs: set[str]) -> bool:
        """检查文件是否被 diff 中的引用提到"""
        file_name = Path(file_path).stem  # 不含扩展名的文件名
        for ref in diff_refs:
            # 文件名匹配或路径子串匹配
            if file_name in ref or ref in file_path:
                return True
        return False
```

##### 效果示例

场景 A：修改 `src/views/plan/index.vue` 的一个 CSS 样式（2 行改动）

```
diff 内容：改了 .container 的 padding
P0 引入：router/index.js（100行） + store/index.js（80行）  → ~1800 tokens
P1 扫描：diff 中没有 import 新模块 → 0 个文件命中 → 不引入
P2 引入：CLAUDE.md（30行）                                   → ~300 tokens
总计：~2100 tokens，轻量通过
```

场景 B：在 `src/views/plan/index.vue` 中新增一个 API 调用组件（50 行改动）

```
diff 内容：import { getPlanList } from '@/api/plan'
P0 引入：router/index.js + store/index.js                   → ~1800 tokens
P1 扫描：diff 引用了 @/api/plan → 命中 src/api/plan.js      → ~500 tokens
         diff 引用了 PlanCard 组件 → 命中 src/components/PlanCard.vue → ~400 tokens
P2 引入：预算剩余 ~1300 → 附带 CLAUDE.md                    → ~300 tokens
总计：~3000 tokens，适度上下文
```

场景 C：修改 `config/database.yml` 配置文件

```
P0：无命中（配置文件不在任何 P0 source 的 match 中）
P1：无命中
P2：命中通用规则，附带 CLAUDE.md                             → ~300 tokens
总计：~300 tokens，配置文件不需要重上下文
```

#### 大规模代码提交的审查策略

核心问题：不定时提交、项目初期、代码重构等场景下，diff 本身可能就是几千行。这时问题不只是"上下文够不够"，而是**LLM 面对超长 diff 时审查质量会急剧下降**（"lost in the middle"效应），塞再多上下文也没用。

所以不能靠堆 token，要**换策略**。

##### Diff 规模分级与对应策略

```
                     diff 行数（变更行，非文件行）
                     │
    0 ────── 200 ──── 800 ──── 2000 ──── ∞
    │  小改动  │  中等改动  │  大改动   │  巨量改动
    │          │           │          │
    │ 单次审查  │ 单次审查   │ 分块审查  │ 分层筛选
    │ 全量上下文│ 自适应上下文│ 按文件分组 │ 两轮策略
    │          │           │          │
    ▼          ▼           ▼          ▼
   精细审查   标准审查    分组审查    先筛后审
```

##### 策略 1：中等改动（200-800 行）— 自适应预算

上下文预算随 diff 规模自动上调，P0/P1/P2 的渐进逻辑不变，只是桶变大了。

```python
def resolve_budget(diff_lines: int, config_budget: BudgetConfig) -> int:
    """根据 diff 规模自动计算上下文预算"""
    if diff_lines < 200:
        return config_budget.default    # 4000
    elif diff_lines < 800:
        return config_budget.medium     # 8000
    elif diff_lines < 2000:
        return config_budget.large      # 12000
    else:
        return config_budget.max        # 16000
```

##### 策略 2：大改动（800-2000 行）— 按文件分组审查

不再把整个 diff 一次性送给 LLM，而是按文件或目录分组，每组独立审查后合并报告。

```python
class GroupedReviewer:
    """大 diff 分组审查"""
    
    def review(self, diff: str, changed_files: list[str]) -> ReviewResult:
        # 1. 按目录/模块分组
        groups = self._group_files(changed_files)
        #   例如：
        #   Group A: src/views/plan/*.vue      (3 个文件, 400 行)
        #   Group B: src/api/plan.js + src/store/plan.js  (2 个文件, 200 行)
        #   Group C: src/utils/*.js            (1 个文件, 300 行)
        
        # 2. 每组独立审查（各自带独立的上下文）
        group_results = []
        for group in groups:
            group_diff = self._extract_group_diff(diff, group.files)
            group_context = self._collect_context(group.files)  # 只收集该组的上下文
            result = self.llm.review(group_diff, group_context)
            group_results.append(result)
        
        # 3. 合并报告
        return self._merge_results(group_results)
    
    def _group_files(self, files: list[str]) -> list[FileGroup]:
        """按目录和关联关系分组"""
        groups = defaultdict(list)
        for f in files:
            # 按一级目录分组（可自定义分组策略）
            key = Path(f).parts[1] if len(Path(f).parts) > 1 else "root"
            groups[key].append(f)
        return [FileGroup(files=fs) for fs in groups.values()]
```

效果：每组 200-500 行 diff + 适量上下文，LLM 审查质量接近小改动场景。组与组之间互不干扰。

##### 策略 3：巨量改动（2000+ 行）— 两轮筛选策略

项目初期、大规模重构、不定时提交等场景。直接审查几千行 diff 既慢又不可靠。

**第一轮：快速扫描（快而粗）**——用一个小模型或低 token 预算，快速标记高风险文件。

```
输入：所有变更文件的文件名 + 变更统计（行数、新增/删除/修改比例）
      + 每个文件的前 10 行（抓 import/require 了解文件用途）
处理：轻量 LLM 调用
输出：每个文件的风险评级（高/中/低）和关注点
```

```python
class TriagePass:
    """第一轮：快速筛选"""
    
    def triage(self, diff_stats: list[FileStat]) -> list[FileRisk]:
        prompt = f"""以下是本次提交的变更文件统计，请快速评估每个文件的风险等级。

{self._format_stats(diff_stats)}

对每个文件输出：
- 风险等级：HIGH / MEDIUM / LOW
- 关注点：一句话说明可能存在的问题方向

评估依据：
- 大量删除的文件（可能丢失逻辑）
- 新增的大文件（可能引入大量未经审查的代码）
- 涉及安全相关的文件（auth、crypto、权限）
- 涉及数据层的文件（SQL、API、数据库操作）
- 配置/环境文件的变更"""
        
        return self._parse_triage(self.llm.review(prompt))
```

**第二轮：针对审查（精而深）**——只对第一轮标记为 HIGH 的文件做完整审查。

```python
class FocusedReviewPass:
    """第二轮：只审查高风险文件"""
    
    def review(self, triage_result: list[FileRisk], diff: str) -> ReviewResult:
        high_risk_files = [t.file for t in triage_result if t.risk == "HIGH"]
        
        if not high_risk_files:
            # 没有高风险文件，对 MEDIUM 文件做简化审查
            medium_files = [t.file for t in triage_result if t.risk == "MEDIUM"]
            return self._quick_review(medium_files, diff)
        
        # 对高风险文件做完整审查（分组 + 全量上下文）
        return self._full_review(high_risk_files, diff)
```

##### 配置

```yaml
# .ai-review.yaml

context:
  budget:
    default: 4000
    medium: 8000
    large: 12000
    max: 16000

# 审查策略配置
review:
  strategy:
    # 分组审查阈值：超过此行数启用分组模式
    group_threshold: 800
    # 分组方式：by_directory（按目录）/ by_module（按模块，需配置）/ by_file（逐文件）
    group_by: "by_directory"
    
    # 两轮筛选阈值：超过此行数启用筛选模式
    triage_threshold: 2000
    # 第一轮使用的模型（可以用更快的小模型）
    triage_model: null  # null = 使用同一个模型；也可指定 "ollama:qwen2.5-coder:1.5b" 等小模型
    
    # 巨量提交的行为
    on_massive:
      # warn: 警告后继续审查 / skip: 跳过审查 / force: 强制完整审查
      action: "warn"
      message: "⚠️ 本次提交变更量较大（{lines} 行），建议拆分为多次提交以提高审查质量。"
```

##### 各策略对比

```
┌──────────┬──────────┬──────────┬──────────────┐
│          │ 小改动    │ 中等改动  │ 大/巨量改动    │
│          │ <200 行   │ 200-800行│ >800 行       │
├──────────┼──────────┼──────────┼──────────────┤
│ 审查次数  │ 1 次 LLM │ 1 次 LLM │ 2-N 次 LLM   │
│ 上下文    │ 4000 tok │ 自适应    │ 每组独立预算  │
│ 审查策略  │ 全量     │ 全量      │ 分组/筛选     │
│ 耗时      │ 快       │ 中       │ 较长但可靠    │
│ 质量      │ 高       │ 高       │ 高（因为聚焦）│
│ 无策略时  │ 高       │ 中       │ 低（lost in   │
│          │          │          │  the middle） │
└──────────┴──────────┴──────────┴──────────────┘
```

#### Layer 3：Agent 协作提示（可选）

```python
class AgentHint:
    """检测 agent 环境并输出上下文分析建议"""
    
    def get_hint(self, changed_files: list[str]) -> str | None:
        # 检测是否有 agent 环境
        has_claude = shutil.which("claude") is not None
        has_cursor = os.environ.get("CURSOR_TRACE_ID") is not None
        
        if not (has_claude or has_cursor):
            return None
        
        return (
            f"💡 检测到您在使用 AI Agent。建议让 Agent 分析以下上下文以获得更深入的审查：\n"
            f"   - 变更文件 {changed_files} 的依赖链和调用关系\n"
            f"   - 相关模块的接口定义和类型约束\n"
            f"   - 最近与此功能相关的讨论或 issue\n"
            f"   提示：可将此审查报告作为 Agent 的输入，让其做增量分析。"
        )
```

#### 为什么这个设计更好

| 对比 | 固定配置全量注入 | 渐进式按需采集（新方案） |
|------|----------------|----------------------|
| 小改动 | 塞入全套上下文，浪费 token | P0 骨架 + P1 不命中 = 轻量通过 |
| 大改动 | 同上 | P0 + P1 按需命中 = 适度上下文 |
| 配置文件 | 可能误注入不需要的上下文 | 不命中任何 source = 最小上下文 |
| glob 展开 50 个文件 | 全部读取再截断 | P1 先过滤 diff 相关性，只引入命中项 |
| 通用性 | 差（每种语言/框架需单独适配） | 好（配置驱动 + diff 引用分析通用） |
| 维护成本 | 低但僵化 | 低且灵活（用户自行调整优先级和预算） |

#### 审查速度与开发者体验策略

前面的设计一直在优化"审查质量"，但忽略了一个致命问题：**pre-commit 是阻塞式的，开发者就在终端等着**。审查越深入 → LLM 调用越多次 → 耗时越长 → 紧急修复时无法快速上线。

核心认知：**不应该在 pre-commit 阶段做所有事情**。应该把审查职责分散到不同阶段，让 pre-commit 只做"秒级快筛"，深度审查放到不阻塞开发者的环节。

##### 三阶段审查体系

```
开发者操作流程：
                                                          ┌─────────────┐
 git add → git commit → git push → 创建 PR → 合并到主分支    │   异步通知    │
    │          │            │          │          │         │ (飞书/钉钉)  │
    │          │            │          │          │         └──────┬──────┘
    │          ▼            │          │          │                │
    │    ┌──────────┐       │          │          │                │
    │    │ 快筛阶段  │       │          │          │                │
    │    │ < 5 秒    │       │          │          │                │
    │    │ 只查致命   │       │          │          │                │
    │    └──────────┘       │          │          │                │
    │          │            │          │          │                │
    │     commit 通过       │          │          │                │
    │                       ▼          │          │                │
    │              ┌──────────────┐    │          │                │
    │              │ 异步审查      │    │          │                │
    │              │ 后台运行      │    │          │                │
    │              │ 不阻塞       │    │          │                │
    │              │ 完整审查      │    │          │                │
    │              └──────────────┘    │          │                │
    │                    │             │          │                │
    │              结果推送到通知       │          │                │
    │                       │          ▼          │                │
    │                       │   ┌──────────┐     │                │
    │                       │   │ PR 审查   │     │                │
    │                       │   │ 完整深度  │     │                │
    │                       │   │ 审查      │     │                │
    │                       │   └──────────┘     │                │
    │                       │        │           │                │
    └───────────────────────┴────────┴───────────┘
```

##### 阶段 1：pre-commit 快筛（秒级，阻塞式）

**设计目标**：5 秒内完成，只拦截真正的致命问题，其余全部放行。

不是"审查变快了"，而是**审查范围收窄了**——pre-commit 只检查安全漏洞、明显 bug、凭证泄露这类"不拦就会出事故"的问题。

```yaml
# .ai-review.yaml

hooks:
  pre_commit:
    mode: "fast"             # fast = 只做快筛，full = 完整审查（不推荐）
    timeout: 10              # 超时时间（秒），超时自动放行
    block_on:                # 只有这些级别的问题才阻断提交
      - "CRITICAL"           # 安全漏洞、凭证泄露
      - "ERROR"              # 明显的逻辑错误（如语法错误、类型不匹配）
    pass_through:            # 这些级别仅警告，不阻断
      - "WARNING"
      - "INFO"
    # 快筛使用的规则：只检查 severity=error 的规则
    rules_filter:
      severities: ["error"]
    # 快筛不附带上下文，只有 diff + 规则
    context: false
```

```python
class FastScreener:
    """pre-commit 快筛：秒级，只拦致命问题"""
    
    def screen(self, diff: str, rules: list[Rule]) -> ScreenResult:
        # 1. 只取 severity=error 的规则
        critical_rules = [r for r in rules if r.severity == "error"]
        
        # 2. 构建精简 prompt（无上下文，只有 diff + 规则）
        prompt = self._build_fast_prompt(diff, critical_rules)
        
        # 3. 调用 LLM（带超时）
        try:
            result = self.llm.review(prompt, timeout=10)
        except TimeoutError:
            # 超时 = 放行（不阻断开发者）
            return ScreenResult(action="PASS", reason="审查超时，自动放行")
        
        # 4. 只有 CRITICAL/ERROR 才阻断
        if result.status in ["CRITICAL", "ERROR"]:
            return ScreenResult(action="BLOCK", issues=result.issues)
        
        return ScreenResult(action="PASS", warnings=result.warnings)
```

**为什么能做到快**：
- 不收集上下文（省掉文件读取）
- 只注入 error 级别的规则（prompt 更短）
- 小模型就能做（如 Ollama 上的 7B 模型）
- 目标不是"发现所有问题"，而是"拦住最致命的"

##### 阶段 2：post-commit 异步审查（不阻塞）

commit 已通过，开发者在继续写代码，后台静默跑完整审查。

```python
class AsyncReviewer:
    """post-commit 异步审查：不阻塞，结果推送"""
    
    def review_async(self, commit_sha: str):
        """后台异步执行完整审查"""
        # 1. 获取完整 diff
        diff = git(f"diff {commit_sha}^ {commit_sha}")
        
        # 2. 完整上下文采集 + 全量规则
        context = self.collector.collect(changed_files, diff)
        rules = self.rule_engine.match(changed_files)
        
        # 3. 根据 diff 规模选择策略（分组/筛选）
        strategy = self._pick_strategy(diff)
        result = strategy.review(diff, context, rules)
        
        # 4. 生成报告并推送
        report = self.reporter.generate(result, commit_sha)
        self.notifier.send(report)  # 飞书/钉钉/终端通知
        
        # 5. 保存报告（后续可查看）
        self.reporter.save(report)
```

触发方式：通过 git post-commit hook 或 pre-commit hook 的 `&` 后台执行。

```bash
# .git/hooks/post-commit
# 异步执行完整审查，不阻塞开发者
nohup ai-review async --commit $(git rev-parse HEAD) > /dev/null 2>&1 &
```

##### 阶段 3：PR 审查（主动触发 / CI 集成）

最完整的审查发生在 PR 阶段，此时时间不是问题。

```bash
# 手动触发全量审查
ai-review check --base main --full

# CI 集成（如 GitHub Actions）
ai-review check --base origin/main --format json --output review.json
```

##### 紧急修复的快速通道

```bash
# 方式 1：commit 时加关键词自动跳过快筛
git commit -m "hotfix: 紧急修复线上支付失败问题"
# 提交信息匹配 hotfix/urgent/critical 关键词 → 自动跳过快筛

# 方式 2：显式跳过
git commit --no-verify                    # 跳过所有 hook（Git 原生）
ai-review check --skip                    # 显式跳过 AI 审查
ai-review check --fast-only               # 只跑快筛（跳过异步完整审查）

# 方式 3：环境变量
EMERGENCY=true git commit -m "fix: xxx"   # 跳过 AI 审查
```

```yaml
# .ai-review.yaml

hooks:
  pre_commit:
    # 紧急修复快速通道
    bypass:
      # commit message 匹配这些关键词时自动跳过
      message_patterns:
        - "hotfix"
        - "urgent"
        - "critical"
        - "紧急"
        - "线上修复"
      # 环境变量
      env_vars:
        - "EMERGENCY"
        - "SKIP_REVIEW"
      # --no-verify 时仍然跑异步审查（不拦但要看）
      no_verify_async: true
```

##### 各场景的时间预期

```
┌─────────────────┬──────────────┬──────────────┬──────────────┐
│ 场景             │ 阶段1 快筛    │ 阶段2 异步   │ 开发者等待    │
│                 │ (pre-commit) │ (post-commit)│              │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ 日常小改动       │ 2-5 秒       │ 后台 10-30秒 │ 几乎无感     │
│ 功能开发         │ 3-8 秒       │ 后台 30-60秒 │ 几乎无感     │
│ 大规模重构       │ 3-8 秒       │ 后台 2-5分钟 │ 几乎无感     │
│ 项目初期大提交   │ 3-8 秒       │ 后台 5-10分  │ 几乎无感     │
│ 紧急修复         │ 跳过/0秒     │ 后台静默审查  │ 零等待       │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ scheme_1 (对比)  │ 10-60 秒     │ 无           │ 全程等待     │
│ 大 diff 时       │ 60-180 秒    │ 无           │ 严重阻塞     │
│ 紧急修复时       │ 仍需等待     │ 无           │ 无法快速上线 │
└─────────────────┴──────────────┴──────────────┴──────────────┘
```

#### 审查记忆与阶段间反馈

##### 问题场景

```
时间线 →

Commit 1: 新增 searchInput 事件绑定，缺防抖
          快筛：无 error → 放行 ✓
          异步审查：WARNING "高频操作缺少防抖" → 推送通知

Commit 2: 新增 filterInput 事件绑定，同样缺防抖
          快筛：只看本次 diff，无 error → 放行 ✓
          异步审查：又一条 WARNING

Commit 3: 新增 tableChange 事件，触发频率极高
          快筛：单看 diff 无 error → 放行 ✓
          → 线上出现重复请求风暴
```

根因：阶段 2 的审查结果没有反馈给阶段 1。快筛每次都像第一次见到这个文件一样。

##### 解决方案：审查记忆文件

每次异步审查完成后，将结果沉淀到一个轻量的**审查记忆文件**中。下次快筛时读取这个文件，动态调整审查严格程度。

```
.ai-review/
├── reports/                    # 审查报告（人类可读）
│   ├── 2024-01-15-abc1234.md
│   └── 2024-01-15-def5678.md
└── memory.json                 # 审查记忆（机器可读）
```

```json
// .ai-review/memory.json — 审查记忆文件
{
  "version": 1,
  "updated_at": "2024-01-15T14:30:00",
  "files": {
    "src/views/plan/index.js": {
      "pending_warnings": [
        {
          "rule_id": "debounce-high-frequency",
          "first_seen": "2024-01-14T10:00:00",
          "count": 3,
          "last_message": "searchInput 和 filterInput 事件均缺少防抖"
        }
      ],
      "risk_score": 7,          // 0-10，累积的风险分
      "last_reviewed": "2024-01-15T14:30:00"
    },
    "src/api/user.js": {
      "pending_warnings": [],
      "risk_score": 0,
      "last_reviewed": "2024-01-15T14:30:00"
    }
  }
}
```

##### 反馈回路：异步结果 → 快筛行为

```python
class ReviewMemory:
    """审查记忆管理"""
    
    def __init__(self, memory_path: str = ".ai-review/memory.json"):
        self.path = memory_path
        self.data = self._load()
    
    def record_async_result(self, result: AsyncReviewResult):
        """异步审查完成后，更新记忆"""
        for file_path, warnings in result.file_warnings.items():
            file_mem = self.data["files"].setdefault(file_path, {
                "pending_warnings": [],
                "risk_score": 0,
            })
            
            for warning in warnings:
                # 同一规则同一文件的 warning 做累加
                existing = self._find_existing(file_mem, warning.rule_id)
                if existing:
                    existing["count"] += 1
                    existing["last_message"] = warning.message
                else:
                    file_mem["pending_warnings"].append({
                        "rule_id": warning.rule_id,
                        "first_seen": result.timestamp,
                        "count": 1,
                        "last_message": warning.message,
                    })
            
            # 重新计算风险分
            file_mem["risk_score"] = self._calc_risk_score(file_mem)
            file_mem["last_reviewed"] = result.timestamp
        
        self._save()
    
    def _calc_risk_score(self, file_mem: dict) -> int:
        """计算文件风险分：基于 warning 数量和重复次数"""
        score = 0
        for w in file_mem["pending_warnings"]:
            # 重复出现的 warning 权重更高
            score += min(w["count"], 5) * 2
        return min(score, 10)  # 上限 10
    
    def get_risk_files(self, threshold: int = 5) -> list[str]:
        """获取风险分超过阈值的文件列表"""
        return [
            f for f, m in self.data["files"].items()
            if m["risk_score"] >= threshold
        ]
    
    def clear_for_file(self, file_path: str):
        """文件被修复后清除记忆（如 PR review 通过）"""
        if file_path in self.data["files"]:
            del self.data["files"][file_path]
            self._save()


class AdaptiveScreener:
    """带记忆的自适应快筛"""
    
    def __init__(self, memory: ReviewMemory):
        self.memory = memory
    
    def screen(self, diff: str, changed_files: list[str], 
               rules: list[Rule]) -> ScreenResult:
        
        # 检查本次变更的文件是否有待处理的 warning 历史
        risk_files = self.memory.get_risk_files(threshold=5)
        has_risk = any(f in risk_files for f in changed_files)
        
        if has_risk:
            # 升级模式：对该文件放宽到 warning 级别也拦截
            return self._enhanced_screen(diff, changed_files, rules)
        else:
            # 标准模式：只拦 error/critical
            return self._fast_screen(diff, rules)
    
    def _enhanced_screen(self, diff, changed_files, rules):
        """增强快筛：对有累积风险的文件更严格"""
        # 取出该文件累积的 pending warnings
        pending_context = ""
        for f in changed_files:
            file_mem = self.memory.data["files"].get(f)
            if file_mem and file_mem["pending_warnings"]:
                warnings_text = "\n".join(
                    f"  - [{w['rule_id']}] 已出现 {w['count']} 次: {w['last_message']}"
                    for w in file_mem["pending_warnings"]
                )
                pending_context += f"\n文件 {f} 的历史审查警告:\n{warnings_text}\n"
        
        # prompt 中注入历史警告，让 LLM 判断是否已经升级为 error
        prompt = f"""请审查以下代码变更。

注意：以下文件有累积的审查警告，请判断本次变更是否使这些问题进一步恶化：

{pending_context}

## 代码变更
{diff}

## 输出要求
如果本次变更使已有警告进一步恶化（如同类问题继续扩散），输出 'BLOCKING'。
否则按正常标准审查。"""
        
        result = self.llm.review(prompt, timeout=15)
        return self._parse_result(result)
```

##### 反馈回路全景

```
   Commit 1                Commit 2                 Commit 3
      │                       │                        │
      ▼                       ▼                        ▼
 ┌─────────┐            ┌─────────┐             ┌──────────┐
 │ 快筛     │            │ 快筛     │             │ 快筛      │
 │ 标准模式 │            │ 标准模式 │             │ 增强模式  │ ← 风险分 ≥ 5
 │ → 放行   │            │ → 放行   │             │ → BLOCK  │
 └─────────┘            └─────────┘             └──────────┘
      │                       │                        │
      ▼                       ▼                        │
 ┌─────────┐            ┌─────────┐                    │
 │ 异步审查 │            │ 异步审查 │                    │
 │ WARNING │            │ WARNING │                    │
 └────┬────┘            └────┬────┘                    │
      │                       │                        │
      ▼                       ▼                        │
 ┌─────────────────────────────────────┐               │
 │         memory.json 更新            │               │
 │                                     │               │
 │ plan/index.js:                      │               │
 │   risk_score: 4 → 7 → 8            │───────────────┘
 │   debounce: count=1 → 2            │  下次快筛时读到风险分 ≥ 5
 │   count=2 的 warning 累积           │  → 切换到增强模式
 └─────────────────────────────────────┘
```

##### 记忆的衰减与清理

```yaml
# .ai-review.yaml

memory:
  enabled: true
  # 记忆衰减：warning 超过 N 天未被再次触发，自动降分
  decay_days: 30
  # 风险分阈值：超过此值时快筛升级为增强模式
  risk_threshold: 5
  # 最大文件记录数（防止文件过大）
  max_tracked_files: 200
```

```python
class ReviewMemory:
    def decay(self):
        """定期衰减：长期未再触发的问题逐渐降低风险分"""
        now = datetime.now()
        for file_path, file_mem in self.data["files"].items():
            surviving = []
            for w in file_mem["pending_warnings"]:
                age_days = (now - parse(w["first_seen"])).days
                if age_days > self.decay_days:
                    continue  # 过老的 warning 自然衰减掉
                surviving.append(w)
            file_mem["pending_warnings"] = surviving
            file_mem["risk_score"] = self._calc_risk_score(file_mem)
```

记忆清理的触发时机：
- warning 对应的代码被删除/修改（通过 diff 检测该行不再存在）→ 清除该条 warning
- PR review 通过 → 清除该文件的记忆
- 超过 `decay_days` 未再触发 → 自然衰减
- 手动清除：`ai-review memory clear --file src/views/plan/index.js`

##### 提醒降级与手动抑制

**问题**：warning 本身不阻断提交，开发者可能因为合理原因选择不改。如果每次 commit 都完整提醒同样的 warning，会造成通知疲劳，最终开发者关闭整个工具。

**策略：逐次降级 + 手动抑制**

```
同一 warning 的提醒演进（以 plan/index.js 的防抖缺失为例）：

第 1 次 commit 涉及该文件:
⚠️ plan/index.vue 有 2 条遗留审查问题（未修复）:
   🔴 [×3] 防抖缺失 — searchInput/filterInput/tableChange
   🟡 [×1] Promise 缺少 catch — 第52行
本次审查: ✅ PASS (3秒)
提示: 输入 ai-review fix 查看修复建议

第 2 次:
⚠️ plan/index.vue: 2 条遗留问题（防抖×3, Promise catch×1）
本次审查: ✅ PASS (2秒)

第 3 次:
ℹ️ plan/index.vue: 2 条遗留问题（已折叠，ai-review status 查看详情）
本次审查: ✅ PASS (2秒)

第 4 次起:
（不再显示，除非风险分变化）
本次审查: ✅ PASS (2秒)
```

memory.json 中增加提醒计数：

```json
{
  "files": {
    "src/views/plan/index.js": {
      "pending_warnings": [
        {
          "rule_id": "debounce-high-frequency",
          "first_seen": "2024-01-14T10:00:00",
          "count": 3,
          "remind_count": 4,
          "remind_state": "suppressed",
          "last_message": "..."
        }
      ],
      "suppressed": [
        {
          "rule_id": "no-settimeout",
          "reason": "legacy code, will refactor in Q2",
          "suppressed_at": "2024-01-15T14:00:00",
          "suppressed_by": "manual"
        }
      ],
      "risk_score": 3,
      "last_reviewed": "2024-01-15T14:30:00"
    }
  }
}
```

提醒状态机：

```
               remind_count: 0         1          2          3           4+
提醒状态:      FULL ──────→ SHORT ────→ MINIMAL ──→ SUPPRESSED ──→ 静默
               完整详情     单行摘要    折叠提示     不主动显示      
                                                 (仅 ai-review status)
```

```python
class ReminderStrategy:
    """提醒降级策略"""
    
    def should_remind(self, warning: WarningRecord) -> str | None:
        # 手动抑制的 warning 永远不提醒
        if warning.remind_state == "manual_suppress":
            return None
        
        count = warning.remind_count
        
        if count == 0:
            return "full"       # 完整详情
        elif count == 1:
            return "short"      # 单行摘要
        elif count == 2:
            return "minimal"    # 折叠提示
        else:
            return None         # 静默，不主动显示
    
    def format_reminder(self, warnings: list[WarningRecord], 
                        mode: str) -> str:
        if mode == "full":
            return self._format_full(warnings)
        elif mode == "short":
            return self._format_short(warnings)
        elif mode == "minimal":
            return self._format_minimal(warnings)
```

**风险分变化时重新激活**：如果同一文件的风险分上升（如同类问题继续扩散、或出现了新的 error），被静默的 warning 会重新以 FULL 模式提醒。这就解决了之前担心的"warning 累积成 error"的问题——静默不是永久忽视，一旦情况恶化会重新提醒。

**手动抑制**：

```bash
# 抑制某个文件某条规则（开发者明确选择不改）
ai-review suppress plan/index.vue debounce-high-frequency \
  --reason "legacy code, 下季度统一重构"

# 抑制某个文件所有 warning
ai-review suppress plan/index.vue --all \
  --reason "历史代码，不在维护范围"

# 查看被抑制的列表
ai-review suppress list

# 取消抑制
ai-review suppress cancel plan/index.vue debounce-high-frequency
```

手动抑制会记录原因和时间，写入 memory.json 的 `suppressed` 字段。被抑制的 warning 不再计入风险分，也不再触发任何提醒。但它仍然被记录着，团队可以通过 `ai-review suppress list` 看到哪些 warning 被谁为什么抑制了——这是一种隐性的团队沟通机制。

**配置**：

```yaml
memory:
  enabled: true
  decay_days: 30
  risk_threshold: 5
  max_tracked_files: 200
  # 提醒降级
  reminder:
    # 降级节奏：每次 commit 涉及该文件时算一次
    full: 1          # 第 1 次完整提醒
    short: 1         # 第 2 次简短提醒
    minimal: 1       # 第 3 次折叠提示
    # 第 4 次起静默，直到风险分变化或手动查看
    # 设为 0 可跳过某个级别
```

### 3.3 规则引擎（自定义规则）

#### 方案选择：结构化元数据 + 选择性提示词注入

为什么不选纯提示词注入？三个问题：

1. **token 浪费**：scheme_1 的 REVIEW_GUIDELINES.md 有 200+ 行前端规范，审查一个 `.go` 后端文件时全部塞入 prompt，既浪费 token 又干扰判断
2. **注意力稀释**：规则越多 LLM 越容易遗漏重点，实测超过 15 条规则后审查质量明显下降
3. **无法按需控制**：不能按文件类型筛选、不能单独开关某条规则、不能调整优先级

混合方案的做法：用 YAML 做规则的元数据索引（适用范围、严重等级、开关），规则内容仍然是自然语言 + good/bad 代码示例。审查时先过滤出当前文件命中的规则，只把相关规则注入 prompt。

#### 规则文件格式

```yaml
# rules/frontend.yaml
name: "前端开发规范"
description: "元HIS 前端项目的代码审查规则"

rules:
  - id: "no-kendo-prefix"
    title: "禁止自定义 class 使用 k- 前缀"
    severity: "error"          # error / warning / info
    enabled: true
    applies_to:                # 文件匹配条件
      extensions: [".html", ".css", ".js", ".vue"]
      # paths: ["src/views/**"]  # 可选：路径 glob 匹配
    description: |
      k- 为 Kendo UI 保留命名空间，自定义 class 使用该前缀会引发样式冲突。
    bad_example: |
      <div class="k-container">...</div>
    good_example: |
      <div class="search-container">...</div>
      <div class="user-profile__avatar">...</div>

  - id: "no-settimeout"
    title: "禁止使用 setTimeout 处理时序性问题"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".js"]
    description: |
      setTimeout 依赖时间猜测，不可靠且难以维护。
      时序性问题统一使用 Promise 或回调函数处理。
    bad_example: |
      setTimeout(function () {
          invented.init.render();
      }, 500);
    good_example: |
      new Promise(resolve => {
          invented.init.target();
          resolve();
      }).then(() => {
          invented.init.render();
      });

  - id: "no-absolute-position"
    title: "禁止无意义地使用 position: absolute"
    severity: "warning"
    enabled: true
    applies_to:
      extensions: [".css", ".html"]
    description: |
      滥用 absolute 导致元素脱离文档流，后续布局只能用 margin 强行撑开空间。
      仅在浮层、徽标、角标等场景使用，且父容器需设置 position: relative。
    bad_example: |
      .tooltip {
          position: absolute;
          top: 10px;
      }
    good_example: |
      .tooltip-wrapper {
          position: relative;
      }
      .tooltip-wrapper .tooltip {
          position: absolute;
          top: -30px;
          left: 50%;
          transform: translateX(-50%);
      }

  - id: "debounce-high-frequency"
    title: "高频操作添加防抖机制"
    severity: "warning"
    enabled: true
    applies_to:
      extensions: [".js"]
      paths: ["src/views/**"]
    description: |
      以下场景必须添加防抖：数据新增操作、Kendo Grid 的 change 事件、搜索框输入触发请求。
    bad_example: |
      $("#searchInput").on("input", function () {
          invented.event.search();
      });
    good_example: |
      var debouncedSearch = _.debounce(function () {
          invented.event.search();
      }, 300);
      $("#searchInput").on("input", debouncedSearch);
```

```yaml
# rules/backend.yaml
name: "后端开发规范"
description: "Go 后端服务的代码审查规则"

rules:
  - id: "go-error-handling"
    title: "必须处理 error 返回值"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".go"]
    description: |
      Go 中所有 error 返回值必须被显式检查，禁止使用 _ 忽略。
    bad_example: |
      result, _ := db.Query("SELECT * FROM users")
    good_example: |
      result, err := db.Query("SELECT * FROM users")
      if err != nil {
          return fmt.Errorf("query users failed: %w", err)
      }
```

#### 规则加载与匹配流程

```python
class RuleEngine:
    """规则引擎：加载、过滤、注入"""
    
    def __init__(self, rules_dir: str = "rules/"):
        self.rules = self._load_rules(rules_dir)
    
    def _load_rules(self, rules_dir: str) -> list[Rule]:
        """加载所有 YAML 规则文件"""
        rules = []
        for yaml_file in Path(rules_dir).glob("*.yaml"):
            data = yaml.safe_load(yaml_file.read_text())
            for r in data.get("rules", []):
                rules.append(Rule(**r))
        return rules
    
    def match(self, changed_files: list[str]) -> list[Rule]:
        """根据变更文件列表，过滤出命中的规则"""
        matched = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            for file in changed_files:
                if self._file_matches(file, rule.applies_to):
                    matched.append(rule)
                    break  # 一条规则只需命中一次
        return matched
    
    def _file_matches(self, file_path: str, applies_to: AppliesTo) -> bool:
        """检查文件是否匹配规则的适用范围"""
        ext = Path(file_path).suffix
        if applies_to.extensions and ext not in applies_to.extensions:
            return False
        if applies_to.paths:
            return any(fnmatch(file_path, p) for p in applies_to.paths)
        return True
    
    def format_for_prompt(self, rules: list[Rule]) -> str:
        """将命中的规则格式化为 prompt 片段"""
        if not rules:
            return "无特定规范，请依据通用最佳实践审查。"
        
        sections = []
        for rule in rules:
            section = f"### [{rule.severity.upper()}] {rule.title}\n\n{rule.description}"
            if rule.bad_example:
                section += f"\n\n**错误示例：**\n```\n{rule.bad_example}\n```"
            if rule.good_example:
                section += f"\n\n**正确示例：**\n```\n{rule.good_example}\n```"
            sections.append(section)
        
        return "\n\n---\n\n".join(sections)
```

#### 规则文件的组织方式

```
project-root/
├── .ai-review.yaml            # 主配置（指定规则目录）
├── rules/                     # 规则文件目录（可提交到 git）
│   ├── frontend.yaml          # 前端规则
│   ├── backend.yaml           # 后端规则
│   ├── security.yaml          # 安全规则（通用）
│   └── performance.yaml       # 性能规则（通用）
└── ...
```

主配置中指定规则目录：

```yaml
# .ai-review.yaml
rules:
  dirs:
    - "rules/"                 # 项目规则
    - "~/.ai-review/rules/"    # 全局规则（个人电脑上的通用规则）
```

#### 兼容方案：直接使用 Markdown 规范文件

如果团队不想维护 YAML 规则，也支持直接引用 scheme_1 风格的 Markdown 文件，但需要通过主配置手动指定适用范围：

```yaml
# .ai-review.yaml
rules:
  dirs: ["rules/"]
  # 兼容模式：直接引用 Markdown 规范
  markdown:
    - file: "REVIEW_GUIDELINES_UI.md"
      applies_to:
        extensions: [".html", ".css", ".js", ".vue"]
    - file: "REVIEW_GUIDELINES_SERVER.md"
      applies_to:
        extensions: [".go"]
```

两种模式可以共存——YAML 规则用于精确控制的结构化规则，Markdown 用于大段的规范文档。

### 3.4 Diff 采集器

```python
class DiffCollector:
    def get_staged_diff(self) -> str:
        """pre-commit 场景：获取暂存区 diff"""
        return run("git diff --cached")
    
    def get_branch_diff(self, base="main") -> str:
        """主动触发场景：获取当前分支相对 base 的全部 diff"""
        return run(f"git diff {base}...HEAD")
    
    def get_file_diff(self, file_path: str) -> str:
        """单文件审查"""
        return run(f"git diff HEAD -- {file_path}")
    
    def get_commit_range_diff(self, from_ref: str, to_ref: str) -> str:
        """指定 commit 范围审查"""
        return run(f"git diff {from_ref} {to_ref}")
```

### 3.5 Prompt 组装器

根据上下文 + diff + **命中的规则**动态组装 prompt（只注入与当前变更文件相关的规则）：

```python
class PromptBuilder:
    def build(self, diff: str, context: Context, rules_prompt: str) -> str:
        return f"""你是一名严格的代码审查专家。请根据提供的上下文和规范审查代码变更。

## 项目结构
{context.project_tree}

## 相关代码上下文
{context.related_code}

## 最近的变更历史
{context.git_log}

## 审查规范
{rules_prompt}

## 代码变更
{diff}

## 输出要求
1. 优先对照上面的审查规范逐条检查
2. 如果存在严重错误、安全漏洞或违反 error 级别规范，第一行输出 'BLOCKING'
3. 如果仅有建议或违反 warning 级别规范，输出 'WARNING'
4. 如果没有问题，输出 'PASS'
5. 每个问题需标注对应的规则 ID
6. 用 Markdown 格式输出"""
```

### 3.6 结果解析与决策

```python
class ReviewResult:
    status: Literal["PASS", "WARNING", "BLOCKING"]
    issues: list[Issue]
    summary: str

class DecisionEngine:
    def parse(self, llm_output: str) -> ReviewResult:
        """解析 LLM 输出为结构化结果"""
        ...
    
    def should_block(self, result: ReviewResult) -> bool:
        """决定是否阻断提交"""
        return result.status == "BLOCKING"
```

---

## 四、触发方式设计

### 4.1 Pre-commit Hook

```bash
#!/bin/sh
# .git/hooks/pre-commit

# 调用 ai-review CLI
ai-review check --pre-commit
exit $?
```

或使用 pre-commit 框架（推荐）：

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ai-code-review
        name: AI Code Review
        entry: ai-review check --pre-commit
        language: python
        stages: [pre-commit]
        pass_filenames: false
```

### 4.2 CLI 主动触发

```bash
# 审查当前暂存区（等价于 pre-commit 手动触发）
ai-review check

# 审查当前分支相对 main 的所有变更
ai-review check --base main

# 审查指定文件
ai-review check --path src/foo.py

# 审查指定 commit 范围
ai-review check --from HEAD~3 --to HEAD

# 仅输出报告，不阻断（用于日常检查）
ai-review check --no-block

# 查看当前配置
ai-review config show

# 初始化配置
ai-review init
```

### 4.3 配置设计理念

配置项越多，学习成本越高。这个工具的目标用户是团队成员，不是配置工程师。

设计原则：**一个 mode 字段决定核心行为，其余全部有合理默认值。** 新用户只需填 LLM 配置 + 选一个 mode 就能跑起来。高级用户可以在 mode 基础上覆盖具体字段。

#### 三种预设模式

一个 `mode` 字段，三种选择，覆盖 90% 的使用场景：

```yaml
# .ai-review.yaml（项目级配置，可提交到 git）
version: 1

# ═══ 必填项 ═══
llm:
  backend: "ollama"
  ollama:
    model: "deepseek-coder-v2"
  # openai_compatible:
  #   base_url: "https://api.deepseek.com/v1"
  #   model: "deepseek-chat"

# ═══ 核心：选一个模式 ═══
# "strict"    — pre-commit 完整审查，阻断所有问题，不跑异步。适合对质量要求极高的团队。
# "balanced"  — pre-commit 快筛(只拦致命) + post-commit 异步完整审查。日常推荐。
# "light"     — pre-commit 最小拦截(仅安全漏洞) + 依赖 PR 审查。适合快速迭代或小团队。
mode: "balanced"

# ═══ 以下全部有默认值，可省略 ═══
# 只有需要调整默认行为时才写。
```

**三种模式的行为对比：**

```
                        strict          balanced        light
                    ┌──────────────┬──────────────┬──────────────┐
pre-commit 审查范围  │ 全量规则      │ 仅 error 规则 │ 仅安全相关    │
pre-commit 上下文   │ 完整上下文    │ 无            │ 无           │
pre-commit 阻断     │ error+warning│ 仅 error      │ 仅 CRITICAL  │
pre-commit 超时     │ 60 秒        │ 10 秒         │ 5 秒         │
post-commit 异步    │ 关闭         │ 开启          │ 开启         │
审查记忆反馈       │ 关闭         │ 开启          │ 开启         │
紧急修复通道       │ 有           │ 有            │ 有           │
适合场景           │ 质量优先团队  │ 日常开发      │ 快速迭代     │
pre-commit 耗时    │ 15-60 秒     │ 2-8 秒        │ 1-3 秒       │
开发者等待感       │ 有感         │ 几乎无感      │ 无感         │
```

**初始化时的引导：**

```bash
$ ai-review init

? 请选择 LLM 后端:
  ❯ Ollama (本地模型，零费用)
    OpenAI 兼容 API (Deepseek/通义千问/...)

? 请选择审查模式:
  ❯ balanced — 快筛+异步，推荐日常使用 (pre-commit 2-8秒)
    strict — 完整审查在 pre-commit 阶段，质量优先 (pre-commit 15-60秒)
    light — 最轻拦截，主要靠 PR 审查 (pre-commit 1-3秒)

✓ 已生成 .ai-review.yaml
✓ 已安装 git hooks (pre-commit + post-commit)
```

#### 高级覆盖：mode 下的微调

选了 mode 之后，默认值已经合理。但如果团队有特定需求，可以覆盖 mode 中的任意字段——**只写要改的，不写就用 mode 的默认值**。

```yaml
# 例 1：balanced 模式，但想让 warning 也阻断
mode: "balanced"
hooks:
  pre_commit:
    block_on: ["CRITICAL", "ERROR", "WARNING"]  # 覆盖默认的只拦 error

# 例 2：strict 模式，但不需要审查 .config 文件
mode: "strict"
exclude:
  - "*.config.js"
  - "webpack.*.js"

# 例 3：light 模式，但想关闭异步审查（只要快筛）
mode: "light"
hooks:
  post_commit:
    enabled: false

# 例 4：balanced 模式，用更小模型做快筛、更大模型做异步
mode: "balanced"
llm:
  backend: "ollama"
  ollama:
    model: "qwen2.5-coder:7b"         # 异步审查用大模型
hooks:
  pre_commit:
    llm_override:                      # 快筛用更快的小模型
      model: "qwen2.5-coder:1.5b"
```

#### 完整配置参考（大多数用户不需要看）

```yaml
# .ai-review.yaml — 完整字段参考
# 所有字段都有默认值，只需覆盖要改的。

version: 1

# ── LLM 配置 ──────────────────────────────
llm:
  backend: "ollama"                    # ollama / openai_compatible
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5-coder:7b"
    timeout: 120
  openai_compatible:
    base_url: "https://api.deepseek.com/v1"
    api_key_env: "DEEPSEEK_API_KEY"    # 从环境变量读
    model: "deepseek-chat"
    timeout: 60

# ── 审查模式 ──────────────────────────────
mode: "balanced"                       # strict / balanced / light

# ── 审查策略（可覆盖 mode 默认值）──────────
review:
  strategy:
    group_threshold: 800               # 超过 N 行启用分组审查
    triage_threshold: 2000             # 超过 N 行启用两轮筛选

# ── Hooks 配置（可覆盖 mode 默认值）────────
hooks:
  pre_commit:
    timeout: 10                        # 秒
    block_on: ["CRITICAL", "ERROR"]    # 阻断的严重级别
    context: false                     # 是否收集上下文
    rules_filter:                      # 快筛时只检查的规则级别
      severities: ["error"]
    bypass:                            # 紧急修复跳过条件
      message_patterns: ["hotfix", "urgent", "critical", "紧急"]
      env_vars: ["EMERGENCY", "SKIP_REVIEW"]
    # llm_override:                    # 可选：快筛用不同模型
    #   model: "qwen2.5-coder:1.5b"
  
  post_commit:
    enabled: true                      # 是否开启异步审查
    # llm_override:                    # 可选：异步用不同模型
    #   model: "deepseek-chat"

# ── 上下文引擎（可覆盖 mode 默认值）────────
context:
  budget:
    default: 4000
    medium: 8000
    large: 12000
    max: 16000
  auto:
    file_tree: true
    git_log: true
    diff_stats: true
    nearby_files: true
  sources: []                          # Layer 2 上下文模板（见 3.2 节）

# ── 审查记忆（可覆盖 mode 默认值）──────────
memory:
  enabled: true                        # balanced/light 默认开启，strict 默认关闭
  decay_days: 30
  risk_threshold: 5

# ── 规则引擎 ──────────────────────────────
rules:
  dirs: ["rules/"]
  markdown: []                         # 兼容 scheme_1 的 Markdown 规范

# ── 通用配置 ──────────────────────────────
exclude:
  - "*.lock"
  - "*.min.js"
  - "*.min.css"
  - "*.png"
  - "*.jpg"
  - "package-lock.json"
  - "yarn.lock"
  - ".env*"

report:
  dir: ".ai-review/reports"
  format: "markdown"
  open_editor: false                   # balanced/light 默认关闭，strict 默认开启
```

---

## 五、输出策略与文件管理

### 5.1 核心原则：推送到人，文件给工具

开发者不主动看本地文件，也不常开 Git 网页。团队主要靠即时通讯推送获取信息。

所以：
- **推送通知是唯一的人机交互界面**——必须自包含，读完就知道该干什么
- **本地文件是给工具自己用的**——memory.json 驱动反馈回路，报告文件用于存档和 CI
- **PR 评论是补充**——给 PR reviewer 看，不是给提交者看的

### 5.2 推送通知设计

通知必须自包含，不含"详见某文件"这类依赖。开发者读完通知就能判断要不要改、改哪里。

```
阶段 2（post-commit）推送模板：
──────────────────────────────────────
⚠️ plan/index.vue — 2 个问题

🔴 [累积 ×3] 防抖缺失
   searchInput / filterInput / tableChange 事件
   均未添加防抖，可能引发重复请求风暴
   规则: debounce-high-frequency

🟡 [新发现] Promise 缺少 catch
   第 52 行，建议追加 .catch(err => console.error(err))

📊 风险分: 8/10 | commit: abc1234
──────────────────────────────────────

阶段 3（push/PR 级）推送模板：
──────────────────────────────────────
🔍 分支审查: feat/plan-management (23 文件, 1,240 行)

🔴 严重问题: 2 个
   · plan/index.vue — 防抖累积风险 (×3)
   · api/plan.js — SQL 注入风险 (参数未转义)

🟡 建议改进: 5 个
   · 3 个文件缺少 error handling
   · 2 个文件建议使用 Promise 替代 callback

📊 整体评估: 需关注 | PR: #142
──────────────────────────────────────
```

### 5.3 本地文件管理

```
.ai-review/                    # 整个目录加入 .gitignore
├── memory.json                # 审查记忆（长期保留，自动衰减）
└── reports/                   # 审查报告（自动清理）
    ├── 2024-01-15-abc1234.md  # 命名: 日期-commitSHA
    └── ...
```

**自动清理策略：**

```python
class ReportCleaner:
    """审查报告自动清理"""
    
    def clean(self, reports_dir: str, config: RetentionConfig):
        for report in Path(reports_dir).glob("*.md"):
            age_days = self._file_age(report)
            
            # PASS 且无 warning 的报告：1 天后删除
            if self._is_clean_pass(report) and age_days > 1:
                report.unlink()
            
            # 有 warning 的报告：7 天后删除
            elif age_days > config.warning_retention_days:
                report.unlink()
            
            # BLOCKING 的报告：30 天后删除
            elif age_days > config.blocking_retention_days:
                report.unlink()
```

```yaml
# .ai-review.yaml
report:
  dir: ".ai-review/reports"
  retention:
    pass_days: 1          # 通过的报告保留 1 天
    warning_days: 7       # 有问题的报告保留 7 天
    blocking_days: 30     # 阻断的报告保留 30 天
  format: "markdown"      # markdown / json（json 用于 CI 管道）
```

**memory.json 不自动删除，只有衰减：** warning 30 天未触发自动降分，风险分归零的文件记录在下次写入时清理。这个文件是工具自身运转的核心数据，不给人看。

### 5.4 输出渠道矩阵

```
                    终端输出    系统通知    推送通知    PR评论    本地报告
                    (必须)     (零配置)   (需配置)   (可选)    (自动管理)
──────────────────────────────────────────────────────────────────────────
阶段1 快筛           ✅ 彩色    ❌          ❌        ❌        ❌
  BLOCKING           🔴 阻断    —           —         —         —
  有遗留warning      🟡 提醒    —           —         —         —
  PASS               🟢 放行    —           —         —         —

阶段2 异步审查       ❌         ✅ 即时     ✅ 自包含   ❌        ✅ 存档
  有问题             —         ⚠️ Toast    ⚠️ 详情    —         📝 7天
  通过               —         可选        可选静默    —         📝 1天

阶段3 PR级审查       ❌         ✅ 汇总     ✅ 汇总    ✅ 行级    ✅ 存档
  有问题             —         🔴 Toast    🔴 详情    💬 评论   📝 30天
  通过               —         可选        ✅ 简短     —         📝 1天
```

### 5.5 零配置触达：系统通知 + commit 时提醒

未配置推送渠道时，审查结果通过两层零配置机制触达开发者。

#### 即时层：系统通知（异步审查完成后）

```python
class SystemNotifier:
    """零配置的操作系统通知"""
    
    def notify(self, title: str, message: str):
        if sys.platform == "win32":
            # Windows Toast 通知
            self._windows_notify(title, message)
        elif sys.platform == "darwin":
            # macOS 通知中心
            subprocess.run([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"'
            ])
        else:
            # Linux notify-send
            subprocess.run(["notify-send", title, message])
    
    def _windows_notify(self, title, message):
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(0)
        $text = $template.GetElementsByTagName("text")
        $text.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $text.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("AI Code Review").Show($toast)
        '''
        subprocess.run(["powershell", "-Command", ps_script],
                       capture_output=True)
```

#### 保底层：下次 commit 时提醒（逐次降级）

系统通知可能被忽略，但开发者下一次 commit 时一定会看终端。此时读取 memory.json，按降级策略输出遗留问题（详见 3.2 节"提醒降级与手动抑制"）。

```bash
# 第 1 次 commit 涉及有遗留问题的文件（FULL 模式）
$ git commit -m "feat: 新增表格列"
🔍 AI Code Review 快筛...

⚠️ plan/index.vue 有 2 条遗留审查问题（未修复）:
   🔴 [×3] 防抖缺失 — searchInput/filterInput/tableChange
   🟡 [×1] Promise 缺少 catch — 第52行

本次审查: ✅ PASS (3秒)
提示: 输入 ai-review fix 查看修复建议

# 第 2 次（SHORT 模式）
$ git commit -m "feat: 新增排序"
🔍 AI Code Review 快筛...
⚠️ plan/index.vue: 2 条遗留问题（防抖×3, Promise catch×1）
本次审查: ✅ PASS (2秒)

# 第 3 次（MINIMAL 模式）
$ git commit -m "fix: 修复样式"
🔍 AI Code Review 快筛...
ℹ️ plan/index.vue: 2 条遗留问题（ai-review status 查看详情）
本次审查: ✅ PASS (2秒)

# 第 4 次起（SUPPRESSED，不再显示）
$ git commit -m "feat: 新增导出"
🔍 AI Code Review 快筛...
✅ PASS (2秒)

# 手动抑制后，彻底不再提醒
$ ai-review suppress plan/index.vue debounce-high-frequency --reason "历史代码，Q2重构"
✓ 已抑制: plan/index.vue / debounce-high-frequency
  原因: 历史代码，Q2重构
```

### 5.5 推送渠道配置

```yaml
# .ai-review.yaml

notify:
  enabled: true
  
  # 阶段2 异步审查通知
  post_commit:
    # always: 每次都推 / on_issue: 仅有问题时推 / silent: 不推
    policy: "on_issue"
    # 通过时的通知（仅 policy=always 时生效）
    include_pass: false
  
  # 阶段3 PR 级审查通知
  push:
    policy: "always"
  
  # 渠道配置
  channels:
    - type: "feishu"
      webhook_env: "FEISHU_WEBHOOK_URL"    # 从环境变量读取
      # 或指定用户私聊
      # target: "user:open_id_xxx"
    
    - type: "dingtalk"
      webhook_env: "DINGTALK_WEBHOOK_URL"
    
    - type: "custom"                        # 自定义 webhook
      url_env: "REVIEW_NOTIFY_URL"
      method: "POST"
```

推送渠道是可扩展的——核心代码只负责生成通知内容，具体发送到哪个渠道通过适配器模式接入。

## 六、项目结构

```
ai-code-review/
├── pyproject.toml              # 项目配置 & 依赖
├── README.md
├── .ai-review.yaml.example     # 配置模板
├── src/
│   └── ai_review/
│       ├── __init__.py
│       ├── cli.py              # CLI 入口（Typer）
│       ├── config.py           # 配置加载、mode 预设合并
│       ├── rules/
│       │   ├── __init__.py
│       │   ├── loader.py       # 规则加载器（YAML + Markdown）
│       │   ├── matcher.py      # 文件类型/路径匹配
│       │   └── formatter.py    # 规则 → prompt 片段格式化
│       ├── collector/
│       │   ├── __init__.py
│       │   ├── diff.py         # Diff 采集器
│       │   └── filter.py       # 文件过滤
│       ├── context/
│       │   ├── __init__.py
│       │   ├── auto.py         # Layer 1: 自动采集（文件树/git log/周边文件）
│       │   ├── template.py     # Layer 2: 渐进式上下文采集（P0/P1/P2）
│       │   └── agent_hint.py   # Layer 3: Agent 协作提示（可选）
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py         # LLM 抽象接口
│       │   ├── ollama.py       # Ollama 实现
│       │   └── openai.py       # OpenAI 兼容实现
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── store.py        # 审查记忆读写（memory.json）
│       │   └── decay.py        # 记忆衰减 & 清理
│       ├── reviewer/
│       │   ├── __init__.py
│       │   ├── screener.py     # 阶段1: 快筛（标准/增强模式）
│       │   ├── async_reviewer.py # 阶段2: 异步增量审查
│       │   ├── pr_reviewer.py  # 阶段3: PR 级完整审查
│       │   ├── strategy.py     # 策略选择（分组/筛选/全量）
│       │   └── parser.py       # 结果解析
│       ├── prompt/
│       │   ├── __init__.py
│       │   └── builder.py      # Prompt 组装
│       ├── output/
│       │   ├── __init__.py
│       │   ├── terminal.py     # 终端彩色输出
│       │   ├── notifier.py     # 推送通知（飞书/钉钉/自定义）
│       │   ├── pr_comment.py   # PR 评论（GitHub/GitLab API）
│       │   └── report.py       # 本地报告生成 + 自动清理
│       └── hooks/
│           ├── __init__.py
│           ├── pre_commit.py   # pre-commit hook 逻辑
│           └── post_commit.py  # post-commit hook 逻辑
├── hooks/
│   ├── pre-commit              # Git hook 脚本（安装用）
│   └── post-commit             # Git hook 脚本（安装用）
└── tests/
    └── ...
```

---

## 七、与你同事方案 (scheme_1) 的对比

| 维度 | scheme_1 (同事方案) | 本方案 |
|------|-------------------|--------|
| LLM 调用方式 | `claude -p` CLI（强依赖 Claude Code） | 直接 HTTP API 调用（无额外依赖） |
| 支持的 LLM | 仅 Claude | Ollama + 任何 OpenAI 兼容 API |
| 上下文检索 | 无（仅传 diff） | 分层上下文引擎（依赖分析 + 可选向量检索） |
| 代码语言 | Shell 脚本 | Python（可测试、可维护、可扩展） |
| 配置管理 | 硬编码在 hook 脚本中 | YAML 配置文件（支持项目级 + 全局级） |
| 审查规范 | 单一 REVIEW_GUIDELINES.md | 结构化规则引擎（YAML+MD），按文件类型/路径匹配，可单独开关 |
| 触发方式 | 仅 pre-commit | pre-commit + CLI 主动触发 + 可扩展 |
| 报告 | 本地 md 文件 | 本地 md + 可选通知（复用飞书通知逻辑） |

---

## 八、技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 生态丰富，AST 库成熟，团队熟悉 |
| CLI 框架 | Typer | 类型安全，自动补全，比 Click 更现代 |
| HTTP 客户端 | httpx | 同步+异步都支持，比 requests 更轻量 |
| YAML 解析 | PyYAML | 标准选择 |
| AST 解析 | 不需要 | 上下文由用户配置驱动，无需语言解析 |
| 向量存储 | 不需要 | 配置模板已满足需求，无需 RAG |

依赖总量控制在 5 个包以内，安装轻量。

---

## 九、实施路线

### Phase 1：最小可用版本（1-2 天）
- [ ] LLM 抽象层（Ollama + OpenAI 兼容）
- [ ] Diff 采集 + 文件过滤
- [ ] 规则引擎（YAML 规则加载 + Markdown 兼容）
- [ ] Prompt 组装 + 结果解析
- [ ] Pre-commit hook 集成
- [ ] CLI 基础命令（check / init / config）

### Phase 2：上下文引擎（1-2 天）
- [ ] Layer 1 自动采集：文件树、git log、diff stats、周边文件
- [ ] Layer 2 配置模板：按文件类型读取用户指定的上下文文件
- [ ] Layer 3 Agent 协作提示（可选）

### Phase 3：增强功能（2-3 天）
- [ ] Level 2 向量检索上下文（可选）
- [ ] 报告格式化优化
- [ ] 通知推送（复用 scheme_1 的飞书通知逻辑）
- [ ] 规则管理 CLI（list / enable / disable）

### Phase 4：打磨（1-2 天）
- [ ] 单元测试 & 集成测试
- [ ] 文档 & 使用指南
- [ ] CI/CD 集成示例

---

## 十、备选方案

如果不想自建，以下是纯开源方案的可选组合：

### 方案 B：git-lrc + Qodo Aware

- **git-lrc**：开源 pre-commit AI 审查，免费无限制，但只支持 Gemini API（需改造）
- **Qodo Aware**（开源）：MCP Server，提供代码库上下文检索
- 缺点：需要自行组装两个工具，且 git-lrc 的 LLM 后端不够灵活

### 方案 C：ai-pre-commit-reviewer

- 开源，支持 OpenAI / Deepseek / Ollama 多后端
- 实现简单，但无上下文检索能力
- 适合快速验证，不适合长期使用

### 结论

**推荐自建方案（本方案）**，原因：
1. 市面上没有同时满足"零费用 + 自定义 LLM + pre-commit + 上下文检索"的现成工具
2. 核心代码量不大（预计 1000-1500 行 Python），自建可控性最强
3. 可以复用你同事 scheme_1 中的审查规范和通知逻辑
