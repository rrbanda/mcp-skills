"""Proxy to fix vLLM/Llama Stack streaming for goose compatibility.
Strips duplicate reasoning/reasoning_content fields from SSE chunks."""
import json
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import StreamingResponse, JSONResponse
from starlette.routing import Route

UPSTREAM = "https://llamastack-llamastack.apps.ocp.v7hjl.sandbox2288.opentlc.com"
CLIENT = httpx.AsyncClient(verify=False, timeout=120.0)


def fix_chunk(data):
    if not data.strip() or data.strip() == "[DONE]":
        return data
    try:
        obj = json.loads(data)
        for c in obj.get("choices", []):
            for k in ("delta", "message"):
                b = c.get(k, {})
                if "reasoning" in b and "reasoning_content" in b:
                    del b["reasoning"]
        return json.dumps(obj)
    except Exception:
        return data


async def proxy(request: Request):
    path = request.path_params["path"]
    body = await request.body()
    hdrs = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }
    url = f"{UPSTREAM}/v1/{path}"

    if request.method == "POST" and body:
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if payload.get("stream"):
            req = CLIENT.build_request("POST", url, content=body, headers=hdrs)
            resp = await CLIENT.send(req, stream=True)

            async def gen():
                try:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            yield f"data: {fix_chunk(line[6:])}\n\n"
                        elif line.strip():
                            yield f"{line}\n\n"
                finally:
                    await resp.aclose()

            return StreamingResponse(gen(), media_type="text/event-stream")
        else:
            resp = await CLIENT.post(url, content=body, headers=hdrs)
            data = resp.json()
            for c in data.get("choices", []):
                m = c.get("message", {})
                if "reasoning" in m and "reasoning_content" in m:
                    del m["reasoning"]
            return JSONResponse(content=data, status_code=resp.status_code)

    resp = await CLIENT.request(request.method, url, content=body, headers=hdrs)
    try:
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(content={"raw": resp.text}, status_code=resp.status_code)


app = Starlette(
    routes=[
        Route(
            "/v1/{path:path}",
            proxy,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )
    ]
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9090)
