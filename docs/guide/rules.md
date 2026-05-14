---
title: "规则系统"
---

# 规则系统

规则系统是 AI Code Review 的核心模块，通过 YAML 规则文件定义代码审查的标准与约束。每条规则包含 ID、标题、严重等级、适用范围和详细描述，用于指导 AI 在审查时关注哪些问题。

## 规则文件格式

规则文件采用 YAML 格式，基本结构如下：

```yaml
name: "规则集名称"
rules:
  - id: "rule-id"
    title: "规则标题"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".py", ".js"]
    description: "规则描述"
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 规则的唯一标识符，用于在审查结果中引用该规则 |
| `title` | string | 是 | 规则的简短标题，便于在报告和通知中快速识别 |
| `severity` | string | 是 | 严重等级，可选值为 `error`、`warning`、`info` |
| `enabled` | boolean | 否 | 是否启用该规则，默认为 `true`。设为 `false` 可临时禁用 |
| `applies_to.extensions` | string[] | 否 | 适用的文件扩展名列表。为空时适用于所有文件类型 |
| `description` | string | 是 | 规则的详细描述，说明该规则要检测的问题及修复建议 |

## Severity 行为

不同的严重等级在审查流程中具有不同的行为表现：

| Severity | 是否阻止提交 | 审查报告中标记为 | 说明 |
| --- | --- | --- | --- |
| `error` | 是，阻止提交 | ERROR | 严重问题，必须在提交前修复 |
| `warning` | 否，不阻止提交 | WARNING | 潜在风险，建议修复但不强制 |
| `info` | 不在 pre-commit 屏幕中显示 | INFO | 仅供了解的信息性提示，在完整报告中可见 |

::: tip 合理设置 Severity
建议仅将真正影响代码质量和安全性的问题设为 `error`，避免过多阻止提交影响开发效率。代码风格类建议使用 `warning`，优化建议使用 `info`。
:::

## 规则示例

### 前端 TypeScript/Vue 规则

```yaml
name: "前端代码规范"
rules:
  - id: "no-console-log"
    title: "禁止使用 console.log"
    severity: "warning"
    enabled: true
    applies_to:
      extensions: [".ts", ".vue", ".js"]
    description: |
      生产代码中不应保留 console.log 调用。
      请使用专业的日志工具（如 winston、pino）替代，
      或在提交前移除所有调试日志。

  - id: "no-any-type"
    title: "禁止使用 any 类型"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".ts", ".vue"]
    description: |
      使用 any 类型会绕过 TypeScript 的类型检查，
      降低代码的类型安全性。应使用具体类型、泛型或 unknown 替代。

  - id: "promise-catch"
    title: "Promise 必须包含错误处理"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".ts", ".js", ".vue"]
    description: |
      所有 Promise 调用链必须包含 .catch() 处理或使用
      try/catch 包裹 async/await，避免未捕获的异常导致运行时错误。
```

### 后端 Python 规则

```yaml
name: "后端安全规范"
rules:
  - id: "no-eval"
    title: "禁止使用 eval()"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".py"]
    description: |
      eval() 函数会执行任意代码，存在严重的代码注入风险。
      如需动态求值，请使用 ast.literal_eval() 或其他安全替代方案。

  - id: "sql-injection"
    title: "检测 SQL 注入风险"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".py"]
    description: |
      禁止使用字符串拼接或 f-string 构建 SQL 查询。
      必须使用参数化查询（parameterized query）或 ORM 提供的查询构建器。

  - id: "no-hardcoded-secrets"
    title: "禁止硬编码密钥和凭证"
    severity: "error"
    enabled: true
    applies_to:
      extensions: [".py"]
    description: |
      禁止在源代码中硬编码 API Key、密码、Token 等敏感信息。
      请使用环境变量或密钥管理服务（如 Vault）进行管理。
```

## 规则匹配

### 扩展名匹配

规则通过 `applies_to.extensions` 字段限定适用范围：

- **精确匹配**：仅对指定扩展名的文件生效，例如 `[".py"]` 仅检查 Python 文件
- **多扩展名**：可同时指定多个扩展名，例如 `[".ts", ".js", ".vue"]` 同时覆盖 TypeScript、JavaScript 和 Vue 文件
- **全文件适用**：当 `extensions` 为空或未设置时，该规则适用于所有文件类型

### Severity 过滤

在审查流程的不同阶段，会根据严重等级进行过滤：

- **Pre-commit 阶段**：仅报告 `error` 和 `warning` 级别的问题，`info` 级别不在此时显示
- **完整报告**：包含所有三个级别的审查结果
- **通知推送**：`error` 级别问题会立即触发系统通知，`warning` 和 `info` 汇总后推送

::: warning 注意
当 `enabled` 设为 `false` 的规则不会被任何阶段加载，即使其 severity 为 `error`。禁用规则等同于暂时移除该规则。
:::
