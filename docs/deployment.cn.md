# Titan Local AI 部署指南

这份指南介绍如何在一台带 NVIDIA GPU 的机器上部署本地模型 API，并通过
Tailscale 让电脑和手机访问。英文版见 `docs/deployment.en.md`。

## 一、架构

```text
电脑 / 手机客户端
        |
     Tailscale
        |
Titan Gateway :18080
        |
llama-server :127.0.0.1:8081
        |
      本地模型 + GPU
```

Gateway 提供：

- OpenAI Chat Completions 兼容接口。
- 桌面、手机、本机分开的 API key。
- 单 GPU 的 FIFO 排队。
- 部署机上的数学 MCP 工具循环。
- 最多 20 轮数学工具调用。
- 手机客户端使用的 SSE 兼容响应。
- Windows 一键启动、停止和状态检查。

`llama-server` 必须只监听 `127.0.0.1:8081`，不要把 8081 暴露给局域网或公网。

## 二、公开仓库安全

下面内容不要提交到 GitHub：

```text
真实 API key
云端 Provider key
Tailscale 身份密钥
模型权重
聊天日志
*.gguf
*.safetensors
*.bin
```

仓库中的 `deployment/config.env` 是脱敏模板，下载后可以直接编辑，但其中的
占位符必须替换成你自己的路径和随机 key。

## 三、安装部署机软件

部署机需要：

- NVIDIA 驱动。
- 支持 CUDA 的 `llama-server`。
- Python 3.11 或更新版本。
- Tailscale。

检查显卡：

```powershell
nvidia-smi
```

加载大模型前关闭 Steam、游戏、浏览器硬件加速页面和其他 GPU 程序。Windows
WDDM 可能会预留显存，即使程序本身没有明显 GPU 占用。

## 四、下载模型

以 Qwen3.8-27B 为例：

```text
https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
```

视觉模型至少需要：

```text
Qwen3.8-27B-Q4_K_M.gguf
mmproj-Qwen3.8-27B-Q8_0.gguf
```

如果使用 MTP，再下载匹配文件：

```text
mtp-Qwen3.8-27B-Q4_0.gguf
```

模型文件放在 Git 仓库之外，例如：

```text
D:\TitanLocalAI\models\
```

模型、视觉投影和 MTP 文件必须与当前 llama.cpp 构建和模型转换匹配。

## 五、配置 `config.env`

仓库已经包含脱敏配置文件：

```text
deployment/config.env
```

用文本编辑器打开并填写：

```text
TITAN_LLAMA_SERVER=你的llama-server.exe路径
TITAN_MODEL=你的模型GGUF路径
TITAN_MMPROJ=你的视觉投影GGUF路径
TITAN_MTP_MODEL=你的MTP GGUF路径
TITAN_MATH_SERVER=项目路径\mcp\math\server.py
TITAN_MATH_CWD=项目路径\mcp\math
```

推荐分别生成三个随机 key：

```text
TITAN_API_KEY_DESKTOP=桌面端随机key
TITAN_API_KEY_PHONE=手机端随机key
TITAN_API_KEY_LOCAL=部署机本地随机key
```

不要直接使用模板中的示例字符串。

关键参数示例：

```text
TITAN_GATEWAY_PORT=18080
TITAN_CONTEXT=160000
TITAN_PARALLEL=1
TITAN_GPU_LAYERS=99999
TITAN_UBATCH=512
TITAN_MAX_TOOL_LOOPS=20
TITAN_MAX_QUEUE_SIZE=2
TITAN_QUEUE_TIMEOUT=1800
```

`TITAN_UBATCH` 是物理批大小，不是上下文长度。不要把它设置成 80000 或
160000。显存不足时，优先降低 `TITAN_BATCH`、`TITAN_UBATCH`，再降低上下文。

## 六、安装 Tailscale

部署机和所有客户端都安装 Tailscale，并登录同一 tailnet。

部署机查看地址：

```powershell
tailscale ip -4
```

客户端使用部署机的 `100.x.y.z` 地址，不要使用公网端口映射。

## 七、配置防火墙

使用管理员 PowerShell 执行：

```powershell
deployment\windows\setup-firewall.ps1
```

脚本会读取 `TITAN_GATEWAY_PORT`，只允许 Tailscale IPv4 网段访问 Gateway。
8081 仍然保持本机访问。

## 八、启动服务

Windows 直接双击：

```text
deployment\windows\start-all.bat
```

或者执行：

```powershell
```

等待两个窗口分别出现：

```text
model loaded
math-mcp-ready
```

查看状态：

```text
deployment\windows\status.bat
```

停止服务：

```text
deployment\windows\stop-all.bat
```

如果部署机还有其他 Python 服务，请先检查 `stop-all.ps1` 的进程匹配规则。

## 九、Ubuntu 和 Arch Linux

给脚本执行权限：

```bash
chmod +x deployment/linux/*.sh
```

一个终端启动模型：

```bash
./deployment/linux/start-llama-server.sh
```

另一个终端启动 Gateway：

```bash
./deployment/linux/start-gateway.sh
```

Linux 使用同一套环境变量和 API 行为。

## 十、测试 API

健康检查不需要 key：

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health
```

模型列表需要 key：

```powershell
$h = @{ Authorization = 'Bearer YOUR_DESKTOP_KEY' }
Invoke-RestMethod http://127.0.0.1:18080/v1/models -Headers $h
```

客户端配置：

```text
API 类型：OpenAI Chat Completions
Base URL：http://部署机Tailscale地址:18080/v1
API key：该客户端对应的 key
Model：GET /v1/models 返回的完整 id
```

先测试纯文本，再测试图片、工具和长上下文。

## 十一、数学 MCP

Gateway 会在部署机启动自己的 `titan-math` stdio MCP，向本地模型注入数学工具，
并自动完成：

```text
模型请求 -> tool call -> Gateway 执行 MCP -> 工具结果 -> 模型最终回答
```

最多循环 20 次：

```text
TITAN_MAX_TOOL_LOOPS=20
```

使用机 OpenCode 也可以拥有自己的数学 MCP。两者是不同机器、不同进程，不会
互相冲突。手机只需要调用 Gateway，不需要自己安装 Python 或 MCP。

## 十二、队列和上下文

Gateway 对单 GPU 使用有界 FIFO 队列：

```text
请求 A：立即执行
请求 B：等待
请求 C：等待
请求 D：队列满，返回 429
```

等待超过 `TITAN_QUEUE_TIMEOUT` 会返回 504。数学工具循环期间仍然占用当前
请求的 GPU lease。

不同客户端的上下文互相独立。队列不会合并会话、泄露聊天内容或覆盖另一个
请求的 KV Cache。Gateway 重启会丢失正在等待的请求。

## 十三、常见问题

### 401

检查客户端是否使用了正确的 key。Gateway 支持：

```http
Authorization: Bearer YOUR_KEY
Authorization: YOUR_KEY
x-api-key: YOUR_KEY
api-key: YOUR_KEY
```

### 400

确认使用的是 Chat Completions，而不是 Responses API。先关闭工具、JSON 模式
和结构化输出，使用纯文本及 `/v1/models` 返回的准确模型 ID。

### 429 或 504

429 表示队列已满，504 表示等待超时。

### 显存不足

关闭其他 GPU 程序，依次降低 `TITAN_BATCH`、`TITAN_UBATCH` 和 `TITAN_CONTEXT`。

### 诊断日志

临时设置：

```text
TITAN_DEBUG_REQUESTS=on
```

重启 Gateway 后复现一次，再改回 `off`。日志只记录请求元数据，不记录 key、
聊天正文或图片内容。
