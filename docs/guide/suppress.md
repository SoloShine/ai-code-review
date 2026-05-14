---
title: "抑制管理"
---

# 抑制管理

## 概述

抑制（Suppress）功能允许你针对特定文件或规则关闭弹窗通知。**抑制不会影响审查本身**——代码审查照常运行，生成的报告仍会包含被抑制的问题，只是跳过 toast 通知弹窗。

## 使用方法

### 抑制特定规则

对某个文件抑制指定规则的通知：

```bash
ai-review suppress src/utils/helper.ts no-console-log --reason "调试阶段暂保留"
```

### 抑制全部规则

对某个文件抑制所有规则的通知：

```bash
ai-review suppress src/legacy/old.ts --all --reason "遗留代码"
```

### 查看抑制列表

查看当前所有已抑制的项目：

```bash
ai-review suppress --list
```

### 取消抑制

取消某个文件上指定规则的抑制：

```bash
ai-review suppress src/utils/helper.ts no-console-log --cancel
```

## 匹配规则

抑制项与 LLM 输出的规则采用**三级匹配策略**，从严格到宽松依次尝试：

### 1. 精确匹配

规则 ID 完全一致（忽略大小写及连字符/下划线差异）即视为匹配。

例如抑制项 `no-console-log` 可匹配 LLM 输出的 `no_console_log`、`No-Console-Log` 等。

### 2. 子串匹配

若未精确命中，则检查抑制项的规则 ID 是否**包含于** LLM 输出的 `rule_id` 中，或者 LLM 输出的 `rule_id` 是否**包含于**抑制项中。

例如抑制项 `console` 可匹配 LLM 输出的 `no-console-log`。

### 3. 关键词匹配

从规则 ID 中提取关键词（例如 `no-console-log` 提取为 `console`、`log`），检查所有关键词是否都出现在问题的消息文本中。

:::tip 提示
抑制不会影响审查本身，只是停止弹窗通知。报告仍会包含被抑制的问题。
:::
