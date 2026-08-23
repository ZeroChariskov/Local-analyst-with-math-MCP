# Titan Local AI Gateway

一个面向个人使用的本地大模型网关项目。

它把部署机上的 `llama-server` 封装成 OpenAI-compatible API，并通过
Tailscale 让电脑、手机等客户端安全访问本地模型。网关还可以在部署机上
启动数学 MCP，让模型自行决定是否调用计算工具。

## 项目结构

```text
客户端
  -> Tailscale
  -> Titan Gateway
      -> llama-server
          -> 本地模型和 GPU
```

项目包含：

- OpenAI Chat Completions 兼容接口。
- 多客户端 API key。
- 单 GPU FIFO 请求队列。
- 部署机 Gateway-side 数学 MCP。
- 最多 20 轮数学工具调用循环。
- SSE 流式响应兼容。
- Windows 一键启动、停止和状态检查脚本。
- Ubuntu 和 Arch Linux 启动脚本。
- OpenCode Provider 和 `local-analyst` Agent 示例。

## 快速开始

1. 在部署机安装 NVIDIA 驱动、CUDA 版 `llama-server`、Python 和 Tailscale。
2. 在部署机和客户端登录同一个 Tailscale 网络。
3. 复制配置模板：

   ```powershell
   Copy-Item deployment\config.example.env deployment\config.env
   ```

4. 编辑 `deployment/config.env`，填写模型路径、MTP 路径、数学 MCP 路径和
   三个客户端 API key。
5. Windows 双击：

   ```text
   deployment\windows\start-all.bat
   ```

6. 等待两个窗口分别出现：

   ```text
   model loaded
   math-mcp-ready
   ```

7. 使用 OpenAI-compatible 客户端访问：

   ```text
   http://<deployment-tailscale-ip>:<gateway-port>/v1
   ```

完整英文部署说明：

```text
docs/deployment.en.md
```

## 模型

本项目不绑定某个模型。只要模型和 `llama-server` 兼容，就可以通过
`deployment/config.env` 配置。

Qwen3.8-27B 是已经验证过的视觉模型示例：

```text
https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
```

推荐的 Qwen 示例文件：

```text
Qwen3.8-27B-Q4_K_M.gguf
mmproj-Qwen3.8-27B-Q8_0.gguf
```

如果启用 MTP，还需要对应的 draft 文件，并确认它和当前 llama.cpp 版本匹配。

## API key

不要复用同一个 key。建议分别配置：

```text
TITAN_API_KEY_DESKTOP=...
TITAN_API_KEY_PHONE=...
TITAN_API_KEY_LOCAL=...
```

这些 key 只写在本地 `deployment/config.env`，不要提交到 GitHub。

## 队列和上下文

Gateway 默认采用：

```text
1 个请求执行中
2 个请求排队
队列满：HTTP 429
等待超时：HTTP 504
```

不同客户端的对话上下文彼此独立，不会互相共享或覆盖。队列只负责调度
GPU，不负责合并会话。

## 安全注意事项

- 不要暴露 `llama-server` 的 8081 端口。
- 不要做公网端口映射。
- 只通过 Tailscale 访问 Gateway。
- `deployment/config.env` in this repository is a placeholder template. Replace
  its values locally and never commit real keys, private paths, model weights,
  or logs.
- 公开仓库前应重新生成所有曾经出现在日志、截图或聊天中的 key。
- 这是个人部署项目，不是经过生产安全审计的公共 SaaS 网关。

## 许可证和第三方模型

本项目代码和 Qwen 模型权重是两个不同的许可对象。使用模型前请阅读对应
模型仓库的许可证和使用条件。`llama.cpp`、MCP、SymPy、Pint 等依赖也分别
遵循各自的许可证。
