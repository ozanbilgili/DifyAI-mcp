"""
Dify Management MCP Server — "Dify-as-Code" bridge.

Exposes Dify Console API operations as MCP tools so Claude Code
can orchestrate Dify workflows programmatically.

Auth: Uses ADMIN_API_KEY + X-WORKSPACE-ID (no cookies/CSRF needed).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx
import yaml
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration (from env)
# ---------------------------------------------------------------------------
DIFY_BASE_URL = os.environ.get("DIFY_BASE_URL", "http://localhost")
DIFY_ADMIN_API_KEY = os.environ["DIFY_ADMIN_API_KEY"]
DIFY_WORKSPACE_ID = os.environ["DIFY_WORKSPACE_ID"]

CONSOLE_API = f"{DIFY_BASE_URL}/console/api"

mcp = FastMCP(
    "Dify Manager",
    instructions=(
        "Dify Management MCP — manage Dify apps and workflows as code. "
        "Use list_apps to discover apps, get_app_dsl to export a workflow as YAML, "
        "update_app_dsl to push YAML changes, and run_workflow_test to execute tests."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {DIFY_ADMIN_API_KEY}",
        "X-WORKSPACE-ID": DIFY_WORKSPACE_ID,
        "Content-Type": "application/json",
    }


def _client() -> httpx.Client:
    return httpx.Client(base_url=CONSOLE_API, headers=_headers(), timeout=60)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_apps(
    page: int = 1,
    limit: int = 20,
    mode: str = "all",
    name: str | None = None,
) -> str:
    """List all Dify applications with pagination.

    Args:
        page: Page number (default 1).
        limit: Items per page (default 20, max 100).
        mode: Filter by app mode — "all", "workflow", "chat", "advanced-chat",
              "agent-chat", "completion".
        name: Optional name filter (substring match).

    Returns:
        JSON with app list including id, name, mode, and description.
    """
    params: dict[str, Any] = {"page": page, "limit": limit, "mode": mode}
    if name:
        params["name"] = name

    with _client() as c:
        r = c.get("/apps", params=params)
        r.raise_for_status()
        data = r.json()

    apps = []
    for app in data.get("data", []):
        apps.append({
            "id": app.get("id"),
            "name": app.get("name"),
            "mode": app.get("mode"),
            "description": app.get("description", ""),
        })

    return json.dumps({
        "page": data.get("page"),
        "total": data.get("total"),
        "has_more": data.get("has_more"),
        "apps": apps,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_app_detail(app_id: str) -> str:
    """Get detailed information about a specific Dify application.

    Args:
        app_id: The UUID of the application.

    Returns:
        JSON with full app details including name, mode, description, model config.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}")
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False, indent=2)


@mcp.tool()
def get_app_dsl(app_id: str, include_secret: bool = False) -> str:
    """Export a Dify application as YAML DSL.

    This is the core "pull" operation — fetches the full workflow definition
    including nodes, edges, and configuration.

    Args:
        app_id: The UUID of the application to export.
        include_secret: Whether to include secret values (API keys etc.) in export.

    Returns:
        The complete DSL as a YAML string.
    """
    params: dict[str, Any] = {"include_secret": str(include_secret).lower()}

    with _client() as c:
        r = c.get(f"/apps/{app_id}/export", params=params)
        if r.status_code == 400:
            return json.dumps({
                "error": "No exportable workflow found. The app may be empty or have no published/draft workflow.",
                "detail": r.json(),
            }, ensure_ascii=False, indent=2)
        r.raise_for_status()
        data = r.json()

    return data.get("data", "")


@mcp.tool()
def update_app_dsl(
    yaml_content: str,
    app_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Import or update a Dify application from YAML DSL.

    If app_id is provided, updates the existing app.
    If app_id is omitted, creates a new app from the DSL.

    Args:
        yaml_content: The complete DSL YAML string to import.
        app_id: Optional — UUID of existing app to overwrite.
        name: Optional — override the app name from DSL.
        description: Optional — override the app description.

    Returns:
        JSON with import result (status, app_id).
    """
    payload: dict[str, Any] = {
        "mode": "yaml-content",
        "yaml_content": yaml_content,
    }
    if app_id:
        payload["app_id"] = app_id
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description

    with _client() as c:
        r = c.post("/apps/imports", json=payload)
        r.raise_for_status()
        result = r.json()

        # If pending (needs dependency confirmation), auto-confirm
        if result.get("status") == "pending":
            import_id = result.get("id")
            if import_id:
                r2 = c.post(f"/apps/imports/{import_id}/confirm")
                r2.raise_for_status()
                result = r2.json()

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def run_workflow_test(
    app_id: str,
    inputs: dict[str, Any] | None = None,
) -> str:
    """Run a workflow draft in test/debug mode and return results.

    Executes the current draft version of a workflow app and returns
    the outputs, status, and any errors.

    Args:
        app_id: The UUID of the workflow application.
        inputs: Dictionary of input variable values for the workflow.

    Returns:
        JSON with workflow run status, outputs, errors, and elapsed time.
    """
    payload: dict[str, Any] = {"inputs": inputs or {}}

    with _client() as c:
        # Stream the SSE response
        events = []
        final_data: dict[str, Any] = {}
        with c.stream(
            "POST",
            f"/apps/{app_id}/workflows/draft/run",
            json=payload,
            timeout=120,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        events.append(event)
                        event_type = event.get("event")
                        if event_type == "workflow_finished":
                            final_data = event.get("data", {})
                        elif event_type == "node_finished":
                            node_data = event.get("data", {})
                            if node_data.get("error"):
                                final_data.setdefault("node_errors", []).append({
                                    "node_id": node_data.get("node_id"),
                                    "node_type": node_data.get("node_type"),
                                    "title": node_data.get("title"),
                                    "error": node_data.get("error"),
                                })
                    except json.JSONDecodeError:
                        continue

    result = {
        "status": final_data.get("status", "unknown"),
        "outputs": final_data.get("outputs"),
        "error": final_data.get("error"),
        "elapsed_time": final_data.get("elapsed_time"),
        "total_tokens": final_data.get("total_tokens"),
        "total_steps": final_data.get("total_steps"),
    }

    if final_data.get("node_errors"):
        result["node_errors"] = final_data["node_errors"]

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def publish_workflow(app_id: str) -> str:
    """Publish the current draft workflow to make it the active version.

    Args:
        app_id: The UUID of the workflow application.

    Returns:
        JSON with the published workflow details.
    """
    with _client() as c:
        r = c.post(f"/apps/{app_id}/workflows/publish")
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False, indent=2)


@mcp.tool()
def get_workflow_draft(app_id: str) -> str:
    """Get the current draft workflow definition (nodes, edges, env vars).

    Args:
        app_id: The UUID of the workflow application.

    Returns:
        JSON with the full draft workflow graph.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflows/draft")
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False, indent=2)


@mcp.tool()
def create_app(
    name: str,
    mode: str = "workflow",
    description: str = "",
) -> str:
    """Create a new empty Dify application.

    Args:
        name: Application name.
        mode: App mode — "workflow", "chat", "advanced-chat", "agent-chat", "completion".
        description: Optional description.

    Returns:
        JSON with the created app details including its id.
    """
    payload = {
        "name": name,
        "mode": mode,
        "description": description,
    }

    with _client() as c:
        r = c.post("/apps", json=payload)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False, indent=2)


@mcp.tool()
def delete_app(app_id: str) -> str:
    """Delete a Dify application.

    Args:
        app_id: The UUID of the application to delete.

    Returns:
        Confirmation message.
    """
    with _client() as c:
        r = c.delete(f"/apps/{app_id}")
        r.raise_for_status()
        return json.dumps({"result": "success", "message": f"App {app_id} deleted."})


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
