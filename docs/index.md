---
layout: home
hero:
  name: "AI Code Review"
  text: "智能代码审查工具"
  tagline: 接入 LLM，提交前自动审查，让每一行代码都经过 AI 审视
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/quick-start
    - theme: alt
      text: 了解更多
      link: /guide/getting-started
    - theme: alt
      text: GitHub
      link: https://github.com/SoloShine/ai-code-review

features:
  - icon: 🛡️
    title: Pre-commit 拦截
    details: 提交前快速筛查，发现安全漏洞、凭证泄露等严重问题直接阻止提交
  - icon: 🔍
    title: Post-commit 深度审查
    details: 提交后异步执行完整审查，生成详细报告和代码修复建议
  - icon: 📏
    title: 自定义规则
    details: YAML 格式规则文件，按文件类型自动匹配，灵活定制审查标准
  - icon: 🧠
    title: 记忆系统
    details: 跨次审查跟踪重复问题，计算风险分数，智能衰减提醒
  - icon: 🔔
    title: 通知中心
    details: 终端 Inbox + HTML 仪表盘 + 系统弹窗三通道提醒
  - icon: 🔌
    title: 多 LLM 后端
    details: 支持 Ollama 本地部署和 OpenAI 兼容 API（智谱、DeepSeek 等）
---
