"""comfyui-mcp: local dev MCP server wrapping the ComfyUI REST API.

Lets Claude submit workflows, poll job status, and *see* generated images so it
can verify image-generation work end to end without a human in the loop.

Target instance is configured via env vars (see .mcp.json):
  COMFYUI_BASE_URL  e.g. http://localhost:8188 (direct) or http://localhost:80 (Caddy)
  COMFYUI_API_KEY   optional Bearer key, required when going through the Caddy proxy
"""

import base64
import os

import httpx
from mcp.server.fastmcp import FastMCP, Image

BASE_URL = os.environ.get("COMFYUI_BASE_URL", "http://localhost:8188").rstrip("/")
API_KEY = os.environ.get("COMFYUI_API_KEY", "").strip()
TIMEOUT = float(os.environ.get("COMFYUI_TIMEOUT", "30"))

mcp = FastMCP("comfyui")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, headers=_headers(), timeout=TIMEOUT)


@mcp.tool()
def instance_health() -> str:
    """Check whether the ComfyUI instance is reachable and report GPU/VRAM/version.

    Use this first when verifying anything image-generation related.
    """
    try:
        with _client() as c:
            r = c.get("/system_stats")
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return f"UNREACHABLE at {BASE_URL}: {e}"

    system = data.get("system", {})
    devices = data.get("devices", [])
    lines = [
        f"OK — {BASE_URL}",
        f"ComfyUI: {system.get('comfyui_version', '?')}  python: {system.get('python_version', '?')}",
    ]
    for d in devices:
        free = d.get("vram_free", 0) / 1e9
        total = d.get("vram_total", 0) / 1e9
        lines.append(f"device: {d.get('name', '?')}  VRAM {free:.1f}/{total:.1f} GB free")
    return "\n".join(lines)


@mcp.tool()
def submit_workflow(workflow_json: dict) -> str:
    """Queue a ComfyUI workflow (API-format prompt graph) for generation.

    Pass the workflow as the prompt graph dict (the 'prompt' field of ComfyUI's
    API format). Returns the prompt_id to poll with get_job_status.
    """
    try:
        with _client() as c:
            r = c.post("/prompt", json={"prompt": workflow_json})
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        return f"REJECTED ({e.response.status_code}): {e.response.text[:500]}"
    except Exception as e:
        return f"ERROR submitting workflow: {e}"

    pid = data.get("prompt_id", "?")
    num = data.get("number", "?")
    return f"queued prompt_id={pid} (queue position {num})"


@mcp.tool()
def get_queue() -> str:
    """Show currently running and pending jobs in the ComfyUI queue."""
    try:
        with _client() as c:
            r = c.get("/queue")
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return f"ERROR reading queue: {e}"

    running = data.get("queue_running", [])
    pending = data.get("queue_pending", [])
    return f"running: {len(running)}  pending: {len(pending)}"


@mcp.tool()
def get_job_status(prompt_id: str) -> str:
    """Report status and output filenames for a submitted prompt_id.

    Returns whether the job is still queued/running or completed, and lists the
    output image filenames (pass these to get_output_image to view them).
    """
    try:
        with _client() as c:
            r = c.get(f"/history/{prompt_id}")
            r.raise_for_status()
            hist = r.json()
    except Exception as e:
        return f"ERROR reading history: {e}"

    entry = hist.get(prompt_id)
    if not entry:
        return f"prompt_id={prompt_id}: not in history yet (still queued/running, or unknown id)"

    status = entry.get("status", {})
    completed = status.get("completed", False)
    status_str = status.get("status_str", "unknown")
    files = _collect_output_files(entry)
    lines = [f"prompt_id={prompt_id}: {status_str} (completed={completed})"]
    if files:
        lines.append("outputs:")
        lines.extend(f"  - {f}" for f in files)
    else:
        lines.append("outputs: none")
    return "\n".join(lines)


@mcp.tool()
def get_recent_history(limit: int = 5) -> str:
    """List the most recent prompts and their output image filenames."""
    try:
        with _client() as c:
            r = c.get("/history", params={"max_items": limit})
            r.raise_for_status()
            hist = r.json()
    except Exception as e:
        return f"ERROR reading history: {e}"

    if not hist:
        return "no history"
    lines = []
    for pid, entry in list(hist.items())[:limit]:
        files = _collect_output_files(entry)
        lines.append(f"{pid}: {', '.join(files) if files else '(no image outputs)'}")
    return "\n".join(lines)


@mcp.tool()
def get_output_image(filename: str, subfolder: str = "", folder_type: str = "output") -> Image:
    """Fetch a generated image so Claude can visually inspect it.

    Use the filename returned by get_job_status / get_recent_history. This lets
    you verify the generation actually produced a correct image, not just that
    the job reported success.
    """
    with _client() as c:
        r = c.get(
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": folder_type},
        )
        r.raise_for_status()
        content = r.content
    fmt = "png" if filename.lower().endswith(".png") else filename.rsplit(".", 1)[-1].lower()
    return Image(data=content, format=fmt)


def _collect_output_files(entry: dict) -> list[str]:
    files: list[str] = []
    outputs = entry.get("outputs", {})
    for node_out in outputs.values():
        for images in node_out.get("images", []):
            name = images.get("filename")
            if name:
                files.append(name)
    return files


if __name__ == "__main__":
    mcp.run()
