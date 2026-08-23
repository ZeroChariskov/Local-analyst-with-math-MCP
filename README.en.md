# Titan Local AI Gateway

A personal local-model Gateway that exposes `llama-server` through an
OpenAI-compatible API. Clients connect over Tailscale; the deployment machine
owns the GPU.

```text
Desktop / phone client -> Tailscale -> Titan Gateway -> llama-server -> GPU
```

Features:

- OpenAI Chat Completions API.
- Separate API keys for desktop, phone, and local clients.
- Bounded FIFO queue for a single GPU.
- Gateway-side `titan-math` MCP client.
- Up to 20 math-tool loops per request.
- SSE compatibility for mobile clients.
- Windows one-click start, stop, and status scripts.
- Ubuntu and Arch Linux startup scripts.
- OpenCode Provider and local Agent examples.

## Quick Start

1. Install an NVIDIA driver, CUDA-enabled `llama-server`, Python, and
   Tailscale on the deployment machine.
2. Install Tailscale on each client and join the same tailnet.
3. Edit the included `deployment/config.env` template.
4. Set model paths, MTP path, math MCP path, port, and three random API keys.
5. On Windows, double-click:

   ```text
   deployment/windows/start-all.bat
   ```

6. Configure any OpenAI-compatible client with:

   ```text
   http://<deployment-tailscale-ip>:<gateway-port>/v1
   ```

7. Use the key assigned to that client and the model ID returned by
   `GET /v1/models`.

The full English guide is `docs/deployment.en.md`. The Chinese guide is
`docs/deployment.md`.

## Security

- Keep `llama-server` on `127.0.0.1:8081`.
- Access the Gateway through Tailscale; do not use public port forwarding.
- Replace every example key before use.
- Never commit model weights, logs, cloud keys, or Tailscale credentials.
- This is a personal deployment project, not a production-audited public SaaS
  Gateway.

## Model Example

Qwen3.8-27B GGUF is a tested multimodal example:

```text
https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
```

The Gateway is configurable and is not hard-coded to Qwen.
