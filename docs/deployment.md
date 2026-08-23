# Deployment Guide

This guide deploys a local OpenAI-compatible model API on a Windows machine
with an NVIDIA GPU. The example model is Qwen3.8-27B GGUF, but the Gateway is
not hard-coded to that model.

## Architecture

```text
Phone / desktop client
        |
     Tailscale
        |
Titan Gateway :18080
        |
llama-server :127.0.0.1:8081
        |
      GPU model
```

The Gateway provides:

- Named API keys for separate clients.
- OpenAI Chat Completions compatibility.
- A bounded FIFO queue for the single GPU.
- Optional Gateway-side `titan-math` MCP orchestration.
- SSE compatibility for clients that request `stream: true`.

`llama-server` must remain localhost-only. Do not expose port 8081.

## Repository Safety

Before publishing, check that these files are not present or tracked:

```text
deployment/config.env
*.log
model weights
real API keys
```

The example configuration contains placeholders only. Never publish a real
Tailscale address, API key, private model path, or personal provider key.

## 1. Prepare The Deployment Machine

Install:

- NVIDIA driver.
- CUDA-enabled `llama-server` build.
- Python 3.11 or newer.
- Tailscale.

Confirm the GPU:

```powershell
nvidia-smi
```

Close Steam, games, browsers with hardware acceleration, and other GPU tools
before loading a large model. WDDM may reserve VRAM even when a process shows
low GPU utilization.

## 2. Download The Model

For the Qwen3.8 example, use:

```text
https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
```

Recommended files:

```text
Qwen3.8-27B-Q4_K_M.gguf
mmproj-Qwen3.8-27B-Q8_0.gguf
```

If using MTP, also download the matching draft file:

```text
mtp-Qwen3.8-27B-Q4_0.gguf
```

Keep model weights outside the Git repository, for example:

```text
D:\TitanLocalAI\models\
```

## 3. Configure The Deployment

From the project root:

```powershell
Copy-Item deployment\config.example.env deployment\config.env
notepad deployment\config.env
```

Set actual paths and keys. Example values:

```text
TITAN_LLAMA_SERVER=__PATH_TO_LLAMA_SERVER__
TITAN_MODEL=__PATH_TO_MODEL_GGUF__
TITAN_MMPROJ=__PATH_TO_MMPROJ_GGUF__
TITAN_MTP_MODEL=__PATH_TO_MTP_GGUF__
TITAN_GATEWAY_PORT=18080
TITAN_CONTEXT=160000
TITAN_GPU_LAYERS=99999
TITAN_MAX_TOOL_LOOPS=20
TITAN_MAX_QUEUE_SIZE=2
TITAN_QUEUE_TIMEOUT=1800
```

Use separate random keys:

```text
TITAN_API_KEY_DESKTOP=replace-with-a-long-random-value
TITAN_API_KEY_PHONE=replace-with-a-different-long-random-value
TITAN_API_KEY_LOCAL=replace-with-a-third-long-random-value
```

Do not use these example strings as real credentials.

Important parameters:

- `TITAN_CONTEXT`: model context slot size. It must match the client limit.
- `TITAN_GPU_LAYERS=99999`: ask llama.cpp to offload every possible layer.
- `TITAN_UBATCH`: physical batch size, not context length. Keep it modest,
  such as `512`; never set it equal to a 160K context by default.
- `TITAN_MAX_TOOL_LOOPS`: maximum Gateway math-tool round trips.
- `TITAN_MAX_QUEUE_SIZE`: number of requests waiting behind the active one.
- `TITAN_QUEUE_TIMEOUT`: maximum queue wait in seconds.

## 4. Install Tailscale

Install Tailscale on every client that should access the API and sign in to
the same tailnet. On the deployment machine:

```powershell
```

Use the deployment machine's `100.x.y.z` address in client configuration.
Do not use a public port forward.

## 5. Configure The Firewall

Run PowerShell as Administrator:

```powershell
deployment\windows\setup-firewall.ps1
```

The script reads `TITAN_GATEWAY_PORT` and allows only the Tailscale IPv4
range. Keep port 8081 blocked externally.

## 6. Start Everything On Windows

Double-click:

```text
```

Or run:

```powershell
```

Two PowerShell windows open. Wait for:

```text
model loaded
math-mcp-ready
```

Check status:

```text
```

Stop services:

```text
```

The stop script is intended for this project machine. Review its process
matching rules if other Python services run there.

## 7. Start On Ubuntu Or Arch

Copy the repository and create `deployment/config.env` as above. Make scripts
executable:

```bash
chmod +x deployment/linux/*.sh
```

Start llama-server in one terminal:

```bash
./deployment/linux/start-llama-server.sh
```

Start the Gateway in another:

```bash
./deployment/linux/start-gateway.sh
```

The Linux scripts use the same environment variables and API behavior.

## 8. Test The API

Health does not require a key:

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health
```

Models require a key:

```powershell
$h = @{ Authorization = 'Bearer YOUR_DESKTOP_KEY' }
Invoke-RestMethod http://127.0.0.1:18080/v1/models -Headers $h
```

From another Tailscale device, replace `127.0.0.1` with the deployment
machine's Tailscale IP.

## 9. Configure An OpenAI Client

Use:

```text
Base URL: http://DEPLOYMENT_TAILSCALE_IP:18080/v1
API key: the key assigned to this client
Model: the id returned by GET /v1/models
API type: OpenAI Chat Completions
```

For mobile clients, start with plain text and `stream: true`. Add images only
after text works. The model ID returned by llama.cpp may contain a Windows
path; use that exact ID if the client requires a model name.

## 10. OpenCode And MCP

OpenCode-side MCP runs in the OpenCode process, not inside llama-server. The
project includes a local stdio math MCP. Install its dependencies wherever
OpenCode runs:

```powershell
python -m pip install -r mcp\math\requirements.txt
```

The Gateway can also start its own independent math MCP process on the
deployment machine. Configure:

```text
TITAN_MATH_ENABLED=on
TITAN_MATH_SERVER=__PATH_TO_PROJECT__\mcp\math\server.py
TITAN_MATH_CWD=__PATH_TO_PROJECT__\mcp\math
TITAN_MAX_TOOL_LOOPS=20
```

The Gateway MCP and OpenCode MCP do not conflict. They are separate processes
on separate hosts. Mobile clients use the Gateway-side MCP loop; OpenCode can
use its own local MCP.

## 11. Queue Behavior

The GPU is serialized:

```text
request A: runs now
request B: waits in FIFO queue
request C: waits in FIFO queue
request D: receives 429 if the queue is full
```

The queue does not share conversation context. Each request has its own
messages and KV-cache state. When a request finishes, the next request starts
with its own prompt. No client sees another client's conversation.

The queue is in Gateway memory. Restarting Gateway loses waiting requests.

## 12. Troubleshooting

### 401 Unauthorized

Check the key assigned to this client. Accepted forms include:

```http
Authorization: Bearer YOUR_KEY
Authorization: YOUR_KEY
x-api-key: YOUR_KEY
api-key: YOUR_KEY
```

### 400 Bad Request

Use OpenAI Chat Completions, not Responses API. Start with plain text, no
tools, no structured output, and the exact model ID from `/v1/models`.

### 409, 429, or 504

The current Gateway version uses FIFO queueing. `429` means the queue is full;
`504` means a request waited too long. A stale older Gateway process may still
return `409`; stop it and restart the current Gateway.

### GPU out of memory

Close GPU applications. Reduce `TITAN_BATCH`, then `TITAN_UBATCH`, then
`TITAN_CONTEXT`. Keep `TITAN_UBATCH` far below the context length.

### Safe request diagnostics

Temporarily set:

```text
TITAN_DEBUG_REQUESTS=on
```

The Gateway logs request metadata but not API keys, chat text, or image data.
Set it back to `off` after diagnosis and restart the Gateway.
