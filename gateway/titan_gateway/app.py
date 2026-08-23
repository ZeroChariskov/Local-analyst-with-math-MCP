from __future__ import annotations

import hashlib
import json
import os
import sys
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


UPSTREAM_URL = os.getenv("TITAN_UPSTREAM_URL", "http://127.0.0.1:8081").rstrip("/")
API_KEY = os.getenv("TITAN_API_KEY", "").strip()
API_KEYS: dict[str, str] = {}
if API_KEY:
    API_KEYS["legacy"] = API_KEY
for env_name, env_value in os.environ.items():
    if env_name.startswith("TITAN_API_KEY_") and env_value.strip():
        API_KEYS[env_name.removeprefix("TITAN_API_KEY_").lower()] = env_value.strip()
HOST = os.getenv("TITAN_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.getenv("TITAN_GATEWAY_PORT", "8080"))
UPSTREAM_TIMEOUT = float(os.getenv("TITAN_UPSTREAM_TIMEOUT", "1800"))
DEBUG_REQUESTS = os.getenv("TITAN_DEBUG_REQUESTS", "off").lower() in {"1", "true", "on", "yes"}
MATH_ENABLED = os.getenv("TITAN_MATH_ENABLED", "on").lower() in {"1", "true", "on", "yes"}
MATH_SERVER = os.getenv("TITAN_MATH_SERVER", "").strip()
MATH_CWD = os.getenv("TITAN_MATH_CWD", "").strip() or None
MAX_TOOL_LOOPS = int(os.getenv("TITAN_MAX_TOOL_LOOPS", "20"))
MAX_QUEUE_SIZE = int(os.getenv("TITAN_MAX_QUEUE_SIZE", "2"))
QUEUE_TIMEOUT = float(os.getenv("TITAN_QUEUE_TIMEOUT", "1800"))

if not API_KEYS:
    raise RuntimeError("TITAN_API_KEY or TITAN_API_KEY_<CLIENT> must be set")


class InferenceQueue:
    def __init__(self) -> None:
        self._active = False
        self._pending: deque[asyncio.Future[None]] = deque()
        self._condition = asyncio.Condition()

    def busy(self) -> bool:
        return self._active

    def queued(self) -> int:
        return len(self._pending)

    async def acquire(self) -> None:
        async with self._condition:
            if not self._active and not self._pending:
                self._active = True
                return
            if len(self._pending) >= MAX_QUEUE_SIZE:
                raise HTTPException(status_code=429, detail="inference queue is full")
            ticket = asyncio.get_running_loop().create_future()
            self._pending.append(ticket)
        try:
            await asyncio.wait_for(asyncio.shield(ticket), timeout=QUEUE_TIMEOUT)
        except asyncio.TimeoutError as exc:
            async with self._condition:
                try:
                    self._pending.remove(ticket)
                except ValueError:
                    pass
            raise HTTPException(status_code=504, detail="inference queue wait timed out") from exc
        except asyncio.CancelledError:
            async with self._condition:
                try:
                    self._pending.remove(ticket)
                except ValueError:
                    pass
            raise

    async def release(self) -> None:
        async with self._condition:
            if self._pending:
                ticket = self._pending.popleft()
                self._active = True
                if not ticket.done():
                    ticket.set_result(None)
            else:
                self._active = False


lease = InferenceQueue()
client: httpx.AsyncClient | None = None
math_stdio = None
math_session: ClientSession | None = None
math_tools: list[dict[str, object]] = []


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global client, math_stdio, math_session, math_tools
    client = httpx.AsyncClient(timeout=httpx.Timeout(UPSTREAM_TIMEOUT, connect=10))
    if MATH_ENABLED and MATH_SERVER:
        params = StdioServerParameters(command=sys.executable, args=[MATH_SERVER], cwd=MATH_CWD)
        math_stdio = stdio_client(params)
        read_stream, write_stream = await math_stdio.__aenter__()
        math_session = ClientSession(read_stream, write_stream)
        await math_session.__aenter__()
        await math_session.initialize()
        listed = await math_session.list_tools()
        math_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in listed.tools
        ]
        debug(f"math-mcp-ready tools={[tool['function']['name'] for tool in math_tools]}")
    yield
    if math_session is not None:
        await math_session.__aexit__(None, None, None)
    if math_stdio is not None:
        await math_stdio.__aexit__(None, None, None)
    await client.aclose()


app = FastAPI(title="Titan Local AI Gateway", version="0.1.0", lifespan=lifespan)


@app.options("/{path:path}")
async def cors_preflight(path: str) -> Response:
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, X-API-Key, API-Key",
            "Access-Control-Max-Age": "600",
        },
    )


def debug(message: str) -> None:
    if DEBUG_REQUESTS:
        print(f"[titan-debug] {message}", flush=True)


def request_metadata(request: Request, body: bytes | None = None) -> dict[str, object]:
    authorization = request.headers.get("authorization", "").strip()
    auth_scheme = authorization.split(None, 1)[0] if authorization else "missing"
    auth_value = authorization.split(None, 1)[1] if " " in authorization else authorization
    metadata: dict[str, object] = {
        "method": request.method,
        "path": request.url.path,
        "query": str(request.url.query),
        "header_names": sorted(request.headers.keys()),
        "auth_scheme": auth_scheme,
        "auth_length": len(auth_value),
        "auth_sha256_prefix": hashlib.sha256(auth_value.encode()).hexdigest()[:10] if auth_value else None,
        "content_type": request.headers.get("content-type"),
        "content_length": request.headers.get("content-length"),
    }
    if body:
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                metadata["json_keys"] = sorted(payload.keys())
                for key in ("model", "stream", "max_tokens", "max_completion_tokens", "temperature", "top_p"):
                    if key in payload:
                        metadata[key] = payload[key]
                messages = payload.get("messages")
                if isinstance(messages, list):
                    metadata["message_count"] = len(messages)
                    metadata["message_roles"] = [item.get("role") for item in messages if isinstance(item, dict)]
                    metadata["message_content_types"] = [type(item.get("content")).__name__ for item in messages if isinstance(item, dict)]
                metadata["has_tools"] = bool(payload.get("tools"))
                metadata["has_response_format"] = "response_format" in payload
                metadata["has_reasoning_effort"] = "reasoning_effort" in payload
        except (UnicodeDecodeError, json.JSONDecodeError):
            metadata["body_json"] = "invalid-json"
    return metadata


def authorized(request: Request) -> None:
    authorization = request.headers.get("authorization", "").strip()
    candidates = {
        request.headers.get("x-api-key", "").strip(),
        request.headers.get("api-key", "").strip(),
    }
    if authorization.lower().startswith("bearer "):
        candidates.add(authorization[7:].strip())
    else:
        # Some mobile OpenAI clients omit the Bearer scheme when compatibility
        # mode is disabled. Accept the exact raw key, never an arbitrary value.
        candidates.add(authorization)
    matched_client = next((name for name, key in API_KEYS.items() if key in candidates), None)
    if matched_client is None:
        debug(f"auth-rejected {request_metadata(request)}")
        raise HTTPException(status_code=401, detail="invalid API key")
    debug(f"auth-ok client={matched_client} {request_metadata(request)}")


def response_json(response: httpx.Response) -> dict[str, object]:
    try:
        value = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"invalid upstream JSON: {response.text[:500]}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=502, detail="upstream response is not an object")
    return value


async def call_math_tool(name: str, arguments: str) -> str:
    if math_session is None:
        raise RuntimeError("titan-math MCP is not available")
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid tool arguments: {exc}") from exc
    result = await math_session.call_tool(name, arguments=parsed)
    parts: list[str] = []
    for item in result.content:
        text = getattr(item, "text", None)
        parts.append(text if text is not None else str(item))
    return "\n".join(parts)


async def complete_with_math_tools(payload: dict[str, object]) -> dict[str, object]:
    assert client is not None
    messages = list(payload.get("messages", []))
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be an array")
    request_payload = dict(payload)
    request_payload["messages"] = messages
    request_payload["stream"] = False
    if math_tools:
        request_payload["tools"] = math_tools
        request_payload["tool_choice"] = "auto"

    for loop in range(MAX_TOOL_LOOPS + 1):
        upstream = await client.post(
            f"{UPSTREAM_URL}/v1/chat/completions",
            json=request_payload,
            headers={"content-type": "application/json"},
        )
        if upstream.status_code >= 400:
            debug(f"tool-loop-upstream-error status={upstream.status_code} body={upstream.text[:1000]!r}")
            raise HTTPException(status_code=upstream.status_code, detail=upstream.text[:1000])
        response = response_json(upstream)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return response
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not tool_calls:
            return response
        if loop >= MAX_TOOL_LOOPS:
            raise HTTPException(status_code=508, detail="maximum math tool loops exceeded")

        messages.append(message)
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name")
            arguments = function.get("arguments", "{}")
            if name not in {tool["function"]["name"] for tool in math_tools}:
                raise HTTPException(status_code=400, detail=f"unsupported tool: {name}")
            try:
                result = await call_math_tool(name, arguments)
            except Exception as exc:
                result = json.dumps({"error": str(exc)}, ensure_ascii=True)
            messages.append({"role": "tool", "tool_call_id": tool_call.get("id", ""), "content": result})
        request_payload["messages"] = messages
        debug(f"tool-loop-complete loop={loop + 1} calls={len(tool_calls)}")

    raise HTTPException(status_code=508, detail="maximum math tool loops exceeded")


def sse_from_completion(response: dict[str, object]) -> bytes:
    choices = response.get("choices") or [{}]
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message", {}) if isinstance(choice, dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    reasoning = message.get("reasoning_content") if isinstance(message, dict) else None
    model = response.get("model", "local-model")
    completion_id = response.get("id", "chatcmpl-gateway")
    chunks: list[bytes] = []
    if reasoning:
        chunks.append(("data: " + json.dumps({"id": completion_id, "object": "chat.completion.chunk", "model": model, "choices": [{"index": 0, "delta": {"reasoning_content": reasoning}, "finish_reason": None}]}, ensure_ascii=False) + "\n\n").encode())
    if content:
        chunks.append(("data: " + json.dumps({"id": completion_id, "object": "chat.completion.chunk", "model": model, "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}, ensure_ascii=False) + "\n\n").encode())
    chunks.append(("data: " + json.dumps({"id": completion_id, "object": "chat.completion.chunk", "model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}, ensure_ascii=False) + "\n\n").encode())
    chunks.append(b"data: [DONE]\n\n")
    return b"".join(chunks)


async def upstream_request(request: Request, path: str) -> Response:
    assert client is not None
    body = await request.body()
    debug(f"proxy-request {request_metadata(request, body)}")
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length", "authorization"}
    }
    try:
        upstream = await client.request(
            request.method,
            f"{UPSTREAM_URL}/{path.lstrip('/')}",
            content=body,
            headers=headers,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"llama-server unavailable: {exc}") from exc

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in {"content-length", "transfer-encoding", "connection"}
    }
    if upstream.status_code >= 400:
        debug(f"upstream-error status={upstream.status_code} path=/{path.lstrip('/')} body={upstream.text[:500]!r}")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )


@app.get("/health")
async def health() -> dict[str, object]:
    assert client is not None
    try:
        upstream = await client.get(f"{UPSTREAM_URL}/health")
        upstream_ok = upstream.is_success
    except httpx.HTTPError:
        upstream_ok = False
    return {"ok": upstream_ok, "upstream": UPSTREAM_URL, "busy": lease.busy(), "queued": lease.queued()}


@app.get("/status")
async def status(request: Request) -> dict[str, object]:
    authorized(request)
    return {"available": True, "busy": lease.busy(), "queued": lease.queued(), "upstream": UPSTREAM_URL}


@app.api_route("/v1/models", methods=["GET"])
async def models(request: Request) -> Response:
    authorized(request)
    return await upstream_request(request, "v1/models")


@app.api_route("/v1/chat/completions", methods=["POST"], response_model=None)
async def chat_completions(request: Request) -> Response | StreamingResponse:
    authorized(request)
    await lease.acquire()
    assert client is not None
    body = await request.body()
    debug(f"chat-request {request_metadata(request, body)}")

    if MATH_ENABLED and math_tools:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            await lease.release()
            raise HTTPException(status_code=400, detail="request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            await lease.release()
            raise HTTPException(status_code=400, detail="request body must be a JSON object")
        try:
            result = await complete_with_math_tools(payload)
        finally:
            await lease.release()
        if payload.get("stream") is True:
            return Response(
                content=sse_from_completion(result),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "x-titan-gateway": "1",
                    "cache-control": "no-cache, no-transform",
                    "connection": "keep-alive",
                    "x-accel-buffering": "no",
                    "access-control-allow-origin": "*",
                },
            )
        return Response(
            content=json.dumps(result, ensure_ascii=False).encode("utf-8"),
            status_code=200,
            media_type="application/json",
            headers={"x-titan-gateway": "1", "access-control-allow-origin": "*"},
        )
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length", "authorization"}
    }

    stream_context = client.stream(
        "POST",
        f"{UPSTREAM_URL}/v1/chat/completions",
        content=body,
        headers=headers,
    )
    try:
        stream = await stream_context.__aenter__()
    except httpx.HTTPError as exc:
        await lease.release()
        raise HTTPException(status_code=503, detail=f"llama-server unavailable: {exc}") from exc
    debug(f"chat-upstream status={stream.status_code} content_type={stream.headers.get('content-type')!r}")
    if stream.status_code >= 400:
        try:
            error_body = (await stream.aread()).decode("utf-8", errors="replace")[:1000]
        finally:
            await stream_context.__aexit__(None, None, None)
            await lease.release()
        debug(f"chat-upstream-error status={stream.status_code} body={error_body!r}")
        return Response(
            content=error_body,
            status_code=stream.status_code,
            media_type=stream.headers.get("content-type") or "text/plain",
            headers={"x-titan-gateway": "1"},
        )

    async def body_stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in stream.aiter_raw():
                yield chunk
        finally:
            await lease.release()
            try:
                await stream_context.__aexit__(None, None, None)
            except Exception:
                pass

    content_type = stream.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return StreamingResponse(
            body_stream(),
            status_code=stream.status_code,
            media_type="text/event-stream",
            headers={
                "x-titan-gateway": "1",
                "cache-control": "no-cache, no-transform",
                "connection": "keep-alive",
                "x-accel-buffering": "no",
                "access-control-allow-origin": "*",
                "access-control-allow-headers": "Authorization, Content-Type, X-API-Key, API-Key",
            },
        )

    try:
        content = await stream.aread()
        status_code = stream.status_code
        content_type = stream.headers.get("content-type", "")
    finally:
        await lease.release()
        try:
            await stream_context.__aexit__(None, None, None)
        except Exception:
            pass
    return Response(
        content=content,
        status_code=status_code,
        headers={"x-titan-gateway": "1"},
        media_type=content_type or None,
    )


@app.api_route("/v1", methods=["POST"], response_model=None)
@app.api_route("/v1/", methods=["POST"], response_model=None)
async def chat_compatibility_path(request: Request) -> Response | StreamingResponse:
    """Accept clients that post to the configured /v1 base URL directly."""
    debug(f"compatibility-rewrite {request.method} {request.url.path} -> /v1/chat/completions")
    return await chat_completions(request)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str) -> Response:
    authorized(request)
    return await upstream_request(request, path)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
