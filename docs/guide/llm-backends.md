---
title: "LLM 后端"
---

# LLM 后端

## 概述

AI Code Review 支持两种 LLM 后端：

| 后端 | 类型 | 适用场景 |
| --- | --- | --- |
| **Ollama** | 本地部署 | 隐私优先、离线使用、无 API 费用 |
| **OpenAI Compatible** | 云端 API | 更强模型能力、无需本地 GPU |

两种后端可以在配置文件中切换，也可以通过 `--mode` 参数临时指定。

## Ollama 配置

### 安装 Ollama

请先按照 [Ollama 官方文档](https://ollama.com) 安装并启动 Ollama 服务。安装完成后拉取模型：

```bash
# 拉取推荐模型
ollama pull qwen2.5-coder:7b

# 验证模型已就绪
ollama list
```

### 配置文件

在项目根目录的 `ai-review.yml` 中添加以下配置：

```yaml
llm:
  backend: ollama
  model: qwen2.5-coder:7b
  base_url: http://localhost:11434    # Ollama 默认地址
  timeout: 30                         # 超时时间（秒）
```

### 推荐模型

| 模型 | 参数量 | 说明 |
| --- | --- | --- |
| `qwen2.5-coder:7b` | 7B | 推荐，兼顾速度与质量 |
| `qwen2.5-coder:14b` | 14B | 更高审查质量，需要更多显存 |
| `deepseek-coder-v2:16b` | 16B | 代码理解能力强，资源占用较高 |

::: tip
如果你的机器 GPU 显存不足 8GB，建议使用 `qwen2.5-coder:7b` 或更小的模型。
:::

## OpenAI Compatible 配置

OpenAI Compatible 后端支持所有兼容 OpenAI API 格式的服务商。只需修改 `base_url` 和对应的 API Key 即可切换。

### 配置文件

```yaml
llm:
  backend: openai_compatible
  model: glm-4-flash                  # 根据服务商选择模型
  base_url: https://open.bigmodel.cn/api/coding/paas/v4
  api_key: ${OPENAI_API_KEY}          # 建议使用环境变量
  timeout: 30
```

### 支持的服务商

#### 智谱 GLM

```yaml
llm:
  backend: openai_compatible
  model: glm-4-flash
  base_url: https://open.bigmodel.cn/api/coding/paas/v4
  api_key: ${ZHIPU_API_KEY}
```

#### DeepSeek

```yaml
llm:
  backend: openai_compatible
  model: deepseek-chat
  base_url: https://api.deepseek.com/v1
  api_key: ${DEEPSEEK_API_KEY}
```

#### 通义千问

```yaml
llm:
  backend: openai_compatible
  model: qwen-plus
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  api_key: ${DASHSCOPE_API_KEY}
```

## API Key 管理

建议通过环境变量管理 API Key，避免将密钥写入配置文件或提交到代码仓库。

### 设置环境变量

**Linux / macOS：**

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
export ZHIPU_API_KEY="your-api-key-here"
export DEEPSEEK_API_KEY="your-api-key-here"
export DASHSCOPE_API_KEY="your-api-key-here"
```

**Windows（PowerShell）：**

```powershell
# 临时设置（当前会话有效）
$env:ZHIPU_API_KEY = "your-api-key-here"

# 永久设置（写入用户环境变量）
[Environment]::SetEnvironmentVariable("ZHIPU_API_KEY", "your-api-key-here", "User")
```

::: warning
Windows 用户注意：永久设置环境变量后需要**重启终端**才能生效。
:::

## 连接测试

配置完成后，可以使用以下命令测试 LLM 后端是否正常连接：

```bash
# 测试当前配置的后端
ai-review test-connection

# 指定后端测试
ai-review test-connection --backend ollama
ai-review test-connection --backend openai_compatible
```

成功输出示例：

```
[INFO] 测试 Ollama 连接...
[INFO] 模型: qwen2.5-coder:7b
[INFO] 连接成功！响应延迟: 1.2s
```

失败时会输出具体的错误信息和排查建议。

::: tip 性能参考
**Balanced 模式**下审查会自动分层：Pre-commit 阶段使用 Fast Prompt（约 5-15 秒），Post-commit 阶段使用 Full Prompt（约 10-30 秒），兼顾速度与深度。
:::
