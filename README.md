# Titan Local AI

This project packages a private, single-user local vision-model service for
OpenCode. The model, paths, ports, and client keys are configurable.

The intended layout is:

```text
Deployment machine (RTX Titan 24 GB)
  llama-server -> Titan Gateway -> Tailscale -> OpenCode on another machine
```

The gateway exposes an OpenAI-compatible API, checks named client API keys,
serializes GPU inference through a FIFO queue, and can run a local math MCP
client for tool loops. Both local and remote clients must use the gateway; do
not expose `llama-server` directly.

## Model

Use the GGUF conversion, not the original BF16 Transformers repository:

```text
https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
```

Recommended files:

```text
Qwen3.8-27B-Q4_K_M.gguf
mmproj-Qwen3.8-27B-Q8_0.gguf
```

The model is multimodal and supports image input. Context length, GPU offload,
MTP, and quantization are configured in `deployment/config.env` for the target
hardware.

## Quick Start

1. Install `llama-server` with CUDA support on the deployment machine.
2. Install Tailscale on both machines and sign in to the same tailnet.
3. Copy `deployment/config.example.env` to `deployment/config.env`.
4. Set model paths, llama-server path, named API keys, and the math MCP path.
5. On Windows, double-click `deployment/windows/start-all.bat`; on Linux,
   start the two shell scripts in separate terminals.
6. Configure the OpenAI-compatible client with the Gateway URL and the key
   for that client.

Detailed instructions are in `docs/deployment.md`.

## Components

- `gateway/`: Python reverse proxy with bearer authentication, FIFO queue,
  streaming compatibility, and optional math MCP orchestration.
- `deployment/`: Windows, Ubuntu, and Arch startup/configuration scripts.
- `opencode/`: Provider and Agent examples for OpenCode.
- `mcp/math/`: local, networkless calculator, equation solver, and unit
  conversion MCP.
- `tests/`: health, model, and chat smoke tests.

The local Qwen subagent uses OpenCode's built-in file, search, LSP, and
permission-controlled shell tools. The only extra MCP is the isolated math
server, because exact arithmetic and unit conversion are useful to both the
remote primary model and the local analyst.

## Security model

- `llama-server` listens on localhost only.
- The gateway is the only externally reachable service.
- The gateway requires `Authorization: Bearer <API key>`.
- Requests are serialized; extra requests wait in a bounded FIFO queue.
- The local Agent can make scoped edits, but cannot invoke other Agents,
  access the network, or run arbitrary shell commands.

Do not commit `deployment/config.env`, `deployment/config.quality.env`, model
weights, logs, or any real API key. See `docs/deployment.md` for the full
Windows walkthrough and security notes.
