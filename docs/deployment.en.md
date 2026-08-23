# Titan Local AI Deployment Guide

This guide deploys a local model behind an OpenAI-compatible Gateway. The
deployment machine owns the GPU; desktop and mobile clients connect through
Tailscale.

## Architecture

```text
Desktop / phone OpenAI client
          |
       Tailscale
          |
Titan Gateway :18080
          |
llama-server :127.0.0.1:8081
          |
       Local model + GPU
```

The Gateway provides:

- OpenAI Chat Completions compatibility.
- Separate API keys for separate clients.
- A bounded FIFO queue for a single GPU.
- Optional deployment-side `titan-math` MCP orchestration.
- Up to 20 math-tool round trips per request.
- SSE compatibility for clients requesting `stream: true`.

`llama-server` must listen on localhost only. Do not expose port 8081.

## Security Before Publishing

Never commit any of the following:

```text
deployment/config.env
real API keys
model weights
chat logs
*.gguf
*.safetensors
*.bin
```

The repository contains example configuration files with placeholders. Before
publishing, rotate any key that appeared in a terminal capture, screenshot,
log, issue, or chat message.

## 1. Install Software On The Deployment Machine

Install:

- An NVIDIA driver.
- A CUDA-enabled `llama-server` build.
- Python 3.11 or newer.
- Tailscale.

Check the GPU:

```powershell
nvidia-smi
```

Close Steam, games, browsers using hardware acceleration, and other GPU
programs before loading a large model. Windows WDDM can reserve VRAM even when
the process appears idle.

## 2. Download Model Files

The Qwen3.8-27B example is available at:

```text
https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
```

For a multimodal deployment, download:

```text
Qwen3.8-27B-Q4_K_M.gguf
mmproj-Qwen3.8-27B-Q8_0.gguf
```

If you want MTP speculative decoding, download the matching draft file too:

```text
mtp-Qwen3.8-27B-Q4_0.gguf
```

Keep model files outside the Git repository. The model, projector, and draft
file must match the inference backend and model conversion.

## 3. Configure The Deployment

From the repository root:

```powershell
Copy-Item deployment\config.example.env deployment\config.env
notepad deployment\config.env
```

Fill in the placeholders:

```text
TITAN_LLAMA_SERVER=__PATH_TO_LLAMA_SERVER__
TITAN_MODEL=__PATH_TO_MODEL_GGUF__
TITAN_MMPROJ=__PATH_TO_MMPROJ_GGUF__
TITAN_MTP_MODEL=__PATH_TO_MTP_GGUF__
TITAN_MATH_SERVER=__PATH_TO_PROJECT__\mcp\math\server.py
TITAN_MATH_CWD=__PATH_TO_PROJECT__\mcp\math
```

Recommended client keys:

```text
TITAN_API_KEY_DESKTOP=replace-with-a-long-random-value
TITAN_API_KEY_PHONE=replace-with-a-different-long-random-value
TITAN_API_KEY_LOCAL=replace-with-a-third-long-random-value
```

Do not use the example values as credentials.

Important runtime settings:

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

`TITAN_UBATCH` is a physical batch size. It is not the context length and
should not be set to 80,000 or 160,000 by default.

## 4. Install Tailscale

Install Tailscale on the deployment machine and every client. Log in to the
same tailnet. Find the deployment machine address:

```powershell
tailscale ip -4
```

Use the resulting `100.x.y.z` address from clients. Do not use public port
forwarding or Tailscale Funnel for this personal API.

## 5. Configure The Firewall

Run PowerShell as Administrator:

```powershell
deployment\windows\setup-firewall.ps1
```

The script reads `TITAN_GATEWAY_PORT` and allows the Tailscale IPv4 range.
Port 8081 remains local-only.

## 6. Start On Windows

Double-click:

```text
deployment\windows\start-all.bat
```

Or run:

```powershell
```

Two PowerShell windows will open. Wait for:

```text
model loaded
math-mcp-ready
```

To inspect the service:

```text
```

To stop the project services:

```text
```

Review `stop-all.ps1` if the machine also runs unrelated Python services.

## 7. Start On Ubuntu Or Arch

Create `deployment/config.env` and install Python dependencies as above. Then:

```bash
chmod +x deployment/linux/*.sh
./deployment/linux/start-llama-server.sh
```

In another terminal:

```bash
./deployment/linux/start-gateway.sh
```

The Linux scripts use the same environment variables and API semantics.

## 8. Test The Gateway

Health does not require a key:

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health
```

Model discovery requires a key:

```powershell
$h = @{ Authorization = 'Bearer YOUR_DESKTOP_KEY' }
Invoke-RestMethod http://127.0.0.1:18080/v1/models -Headers $h
```

The model ID returned by this endpoint is the safest model ID to use in a
client configuration.

## 9. Configure Desktop Or Mobile Clients

Use these values:

```text
API type: OpenAI Chat Completions
Base URL: http://DEPLOYMENT_TAILSCALE_IP:18080/v1
API key: the key assigned to this client
Model: the exact id returned by GET /v1/models
```

Start with a short plain-text request. Add images, tools, JSON mode, and long
contexts only after basic text completion works.

For a mobile client, the Gateway can complete its own math-tool loop even if
the client does not implement MCP. The client only needs to send standard Chat
Completions requests.

## 10. Gateway-Side Math MCP

The Gateway can start a private stdio MCP process on the deployment machine.
It discovers the math tools during startup, injects their schemas into model
requests, executes model-generated math tool calls, and sends results back to
the model. The loop is limited by:

```text
TITAN_MAX_TOOL_LOOPS=20
```

The OpenCode-side MCP and Gateway-side MCP do not conflict. They are separate
processes in separate hosts. The Gateway-side MCP is used by phone/direct API
clients; the OpenCode-side MCP is used by OpenCode sessions.

## 11. Queue And Context Behavior

The GPU is serialized by a bounded FIFO queue:

```text
request A: runs now
request B: waits
request C: waits
request D: receives 429 when the queue is full
```

The active request and its math-tool loop retain the GPU lease until they
finish. A waiting request can receive 504 after `TITAN_QUEUE_TIMEOUT` seconds.

Each client request has independent messages and KV-cache state. Queueing does
not merge conversations, expose one client's context to another, or continue
one client's chat history in another client's request.

The queue is in Gateway memory. Restarting the Gateway drops waiting requests.

## 12. Troubleshooting

### 401 Unauthorized

Check the client-specific key. The Gateway accepts these forms:

```http
Authorization: Bearer YOUR_KEY
Authorization: YOUR_KEY
x-api-key: YOUR_KEY
api-key: YOUR_KEY
```

### 400 Bad Request

Use Chat Completions, not the Responses API. Start with plain text, no tools,
no structured output, and the exact model ID from `/v1/models`.

### 429 or 504

`429` means the queue is full. `504` means the request waited too long.

### GPU out of memory

Close other GPU programs. Reduce `TITAN_BATCH`, then `TITAN_UBATCH`, then
`TITAN_CONTEXT`. Keep `TITAN_UBATCH` much smaller than the context length.

### Diagnostic logging

Temporarily set:

```text
TITAN_DEBUG_REQUESTS=on
```

Restart the Gateway, reproduce one request, then set it back to `off`. The
diagnostic output records request metadata but not API keys, chat text, or
image data.
