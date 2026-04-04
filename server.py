"""
Dify Management MCP Server — "Dify-as-Code" bridge.

Exposes Dify Console API operations as MCP tools so Claude Code
can orchestrate Dify workflows programmatically.

Auth: Uses ADMIN_API_KEY + X-WORKSPACE-ID (no cookies/CSRF needed).
"""

from __future__ import annotations

import difflib
import json
import os
import subprocess
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
        "Dify Management MCP — manage Dify apps, workflows, knowledge bases, "
        "models, and tools as code. Full Dify-as-Code orchestration."
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


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ===========================================================================
# 1. APP MANAGEMENT (Core CRUD)
# ===========================================================================

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
        mode: Filter — "all", "workflow", "chat", "advanced-chat", "agent-chat", "completion".
        name: Optional name filter (substring match).
    """
    params: dict[str, Any] = {"page": page, "limit": limit, "mode": mode}
    if name:
        params["name"] = name
    with _client() as c:
        r = c.get("/apps", params=params)
        r.raise_for_status()
        data = r.json()
    apps = [
        {"id": a.get("id"), "name": a.get("name"), "mode": a.get("mode"), "description": a.get("description", "")}
        for a in data.get("data", [])
    ]
    return _json({"page": data.get("page"), "total": data.get("total"), "has_more": data.get("has_more"), "apps": apps})


@mcp.tool()
def get_app_detail(app_id: str) -> str:
    """Get detailed information about a specific Dify application."""
    with _client() as c:
        r = c.get(f"/apps/{app_id}")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def create_app(name: str, mode: str = "workflow", description: str = "") -> str:
    """Create a new empty Dify application.

    Args:
        name: Application name.
        mode: "workflow", "chat", "advanced-chat", "agent-chat", "completion".
        description: Optional description.
    """
    with _client() as c:
        r = c.post("/apps", json={"name": name, "mode": mode, "description": description})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def delete_app(app_id: str) -> str:
    """Delete a Dify application."""
    with _client() as c:
        r = c.delete(f"/apps/{app_id}")
        r.raise_for_status()
        return _json({"result": "success", "message": f"App {app_id} deleted."})


@mcp.tool()
def copy_app(app_id: str, name: str | None = None) -> str:
    """Duplicate an existing application.

    Args:
        app_id: Source app UUID.
        name: Optional new name (defaults to "Copy of <original>").
    """
    payload: dict[str, Any] = {}
    if name:
        payload["name"] = name
    with _client() as c:
        r = c.post(f"/apps/{app_id}/copy", json=payload)
        if r.status_code == 400:
            return _json({"error": "Cannot copy app. It may lack a draft workflow.", "detail": r.json()})
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 2. DSL EXPORT / IMPORT
# ===========================================================================

@mcp.tool()
def get_app_dsl(app_id: str, include_secret: bool = False) -> str:
    """Export a Dify application as YAML DSL.

    Args:
        app_id: The UUID of the application to export.
        include_secret: Include secret values (API keys etc.) in export.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/export", params={"include_secret": str(include_secret).lower()})
        if r.status_code == 400:
            return _json({"error": "No exportable workflow found.", "detail": r.json()})
        r.raise_for_status()
        return r.json().get("data", "")


@mcp.tool()
def update_app_dsl(
    yaml_content: str,
    app_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Import or update a Dify application from YAML DSL.

    Args:
        yaml_content: Complete DSL YAML string.
        app_id: Optional — existing app UUID to overwrite. Omit to create new.
        name: Optional name override.
        description: Optional description override.
    """
    payload: dict[str, Any] = {"mode": "yaml-content", "yaml_content": yaml_content}
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
        if result.get("status") == "pending":
            import_id = result.get("id")
            if import_id:
                r2 = c.post(f"/apps/imports/{import_id}/confirm")
                r2.raise_for_status()
                result = r2.json()
    return _json(result)


# ===========================================================================
# 3. WORKFLOW MANAGEMENT
# ===========================================================================

@mcp.tool()
def get_workflow_draft(app_id: str) -> str:
    """Get the current draft workflow definition (nodes, edges, env vars)."""
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflows/draft")
        if r.status_code == 404:
            return _json({"error": "No draft workflow found. The app may be empty or not a workflow type."})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def publish_workflow(app_id: str) -> str:
    """Publish the current draft workflow to make it the active version."""
    with _client() as c:
        r = c.post(f"/apps/{app_id}/workflows/publish", json={})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def list_workflow_versions(app_id: str, page: int = 1, limit: int = 20) -> str:
    """List all published workflow versions for an app.

    Args:
        app_id: Application UUID.
        page: Page number.
        limit: Items per page.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflows", params={"page": page, "limit": limit})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def restore_workflow_version(app_id: str, workflow_id: str) -> str:
    """Restore a previous workflow version as the current draft.

    Args:
        app_id: Application UUID.
        workflow_id: The workflow version ID to restore.
    """
    with _client() as c:
        r = c.post(f"/apps/{app_id}/workflows/{workflow_id}/restore")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def run_workflow_test(app_id: str, inputs: dict[str, Any] | None = None) -> str:
    """Run a workflow draft in test/debug mode and return results.

    Args:
        app_id: Workflow application UUID.
        inputs: Dictionary of input variable values.
    """
    with _client() as c:
        events = []
        final_data: dict[str, Any] = {}
        with c.stream("POST", f"/apps/{app_id}/workflows/draft/run", json={"inputs": inputs or {}}, timeout=120) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        events.append(event)
                        if event.get("event") == "workflow_finished":
                            final_data = event.get("data", {})
                        elif event.get("event") == "node_finished":
                            nd = event.get("data", {})
                            if nd.get("error"):
                                final_data.setdefault("node_errors", []).append({
                                    "node_id": nd.get("node_id"), "node_type": nd.get("node_type"),
                                    "title": nd.get("title"), "error": nd.get("error"),
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
    return _json(result)


@mcp.tool()
def run_single_node(app_id: str, node_id: str, inputs: dict[str, Any] | None = None) -> str:
    """Run a single node in the draft workflow for testing.

    Args:
        app_id: Application UUID.
        node_id: The node ID to execute.
        inputs: Input values for the node.
    """
    with _client() as c:
        final_data: dict[str, Any] = {}
        with c.stream(
            "POST", f"/apps/{app_id}/workflows/draft/nodes/{node_id}/run",
            json={"inputs": inputs or {}}, timeout=120,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        if event.get("event") == "node_finished":
                            final_data = event.get("data", {})
                    except json.JSONDecodeError:
                        continue
    return _json({
        "node_id": final_data.get("node_id"),
        "title": final_data.get("title"),
        "status": final_data.get("status", "unknown"),
        "outputs": final_data.get("outputs"),
        "error": final_data.get("error"),
        "elapsed_time": final_data.get("elapsed_time"),
    })


@mcp.tool()
def stop_workflow_task(app_id: str, task_id: str) -> str:
    """Stop a running workflow task.

    Args:
        app_id: Application UUID.
        task_id: Task ID from streaming response.
    """
    with _client() as c:
        r = c.post(f"/apps/{app_id}/workflow-runs/tasks/{task_id}/stop", json={"user": "mcp-admin"})
        r.raise_for_status()
        return _json({"result": "success", "message": f"Task {task_id} stopped."})


@mcp.tool()
def get_default_block_configs(app_id: str, block_type: str | None = None) -> str:
    """Get default configuration for workflow node types.

    Args:
        app_id: Application UUID.
        block_type: Specific block type (e.g. "llm", "code", "if-else"). Omit for all.
    """
    with _client() as c:
        path = f"/apps/{app_id}/workflows/default-workflow-block-configs"
        if block_type:
            path += f"/{block_type}"
        r = c.get(path)
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 4. WORKFLOW RUNS & LOGS
# ===========================================================================

@mcp.tool()
def get_workflow_runs(
    app_id: str,
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
) -> str:
    """List workflow execution history.

    Args:
        app_id: Application UUID.
        page: Page number.
        limit: Items per page.
        status: Filter — "running", "succeeded", "failed", "stopped".
    """
    params: dict[str, Any] = {"page": page, "limit": limit}
    if status:
        params["status"] = status
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflow-runs", params=params)
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_workflow_run_detail(app_id: str, run_id: str) -> str:
    """Get detailed information about a specific workflow run.

    Args:
        app_id: Application UUID.
        run_id: Workflow run ID.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflow-runs/{run_id}")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_node_executions(app_id: str, run_id: str) -> str:
    """Get individual node execution details for a workflow run.

    Args:
        app_id: Application UUID.
        run_id: Workflow run ID.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflow-runs/{run_id}/node-executions")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_workflow_app_logs(app_id: str, page: int = 1, limit: int = 20) -> str:
    """Get workflow application execution logs.

    Args:
        app_id: Application UUID.
        page: Page number.
        limit: Items per page.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflow-app-logs", params={"page": page, "limit": limit})
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 5. STATISTICS
# ===========================================================================

@mcp.tool()
def get_app_statistics(app_id: str, start: str | None = None, end: str | None = None) -> str:
    """Get comprehensive app statistics (messages, users, tokens, costs, response time).

    Args:
        app_id: Application UUID.
        start: Start date (YYYY-MM-DD). Defaults to 7 days ago.
        end: End date (YYYY-MM-DD). Defaults to today.
    """
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end

    stats = {}
    endpoints = [
        ("daily_messages", "statistics/daily-messages"),
        ("daily_conversations", "statistics/daily-conversations"),
        ("daily_end_users", "statistics/daily-end-users"),
        ("token_costs", "statistics/token-costs"),
        ("avg_response_time", "statistics/average-response-time"),
    ]
    with _client() as c:
        for key, path in endpoints:
            try:
                r = c.get(f"/apps/{app_id}/{path}", params=params)
                if r.status_code == 200:
                    stats[key] = r.json()
            except Exception:
                stats[key] = {"error": "Failed to fetch"}
    return _json(stats)


@mcp.tool()
def get_workflow_statistics(app_id: str, start: str | None = None, end: str | None = None) -> str:
    """Get workflow-specific statistics (runs, terminals, token costs).

    Args:
        app_id: Workflow application UUID.
        start: Start date (YYYY-MM-DD).
        end: End date (YYYY-MM-DD).
    """
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end

    stats = {}
    endpoints = [
        ("daily_conversations", "workflow/statistics/daily-conversations"),
        ("daily_terminals", "workflow/statistics/daily-terminals"),
        ("token_costs", "workflow/statistics/token-costs"),
    ]
    with _client() as c:
        for key, path in endpoints:
            try:
                r = c.get(f"/apps/{app_id}/{path}", params=params)
                if r.status_code == 200:
                    stats[key] = r.json()
            except Exception:
                stats[key] = {"error": "Failed to fetch"}
    return _json(stats)


# ===========================================================================
# 6. KNOWLEDGE BASE / DATASET MANAGEMENT
# ===========================================================================

@mcp.tool()
def list_datasets(page: int = 1, limit: int = 20) -> str:
    """List all knowledge base datasets."""
    with _client() as c:
        r = c.get("/datasets", params={"page": page, "limit": limit})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def create_dataset(name: str, description: str = "") -> str:
    """Create a new knowledge base dataset.

    Args:
        name: Dataset name.
        description: Optional description.
    """
    with _client() as c:
        r = c.post("/datasets", json={"name": name, "description": description})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_dataset_detail(dataset_id: str) -> str:
    """Get detailed information about a dataset."""
    with _client() as c:
        r = c.get(f"/datasets/{dataset_id}")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def delete_dataset(dataset_id: str) -> str:
    """Delete a knowledge base dataset."""
    with _client() as c:
        r = c.delete(f"/datasets/{dataset_id}")
        r.raise_for_status()
        return _json({"result": "success", "message": f"Dataset {dataset_id} deleted."})


@mcp.tool()
def list_documents(dataset_id: str, page: int = 1, limit: int = 20) -> str:
    """List documents in a dataset.

    Args:
        dataset_id: Dataset UUID.
        page: Page number.
        limit: Items per page.
    """
    with _client() as c:
        r = c.get(f"/datasets/{dataset_id}/documents", params={"page": page, "limit": limit})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_document_segments(dataset_id: str, document_id: str, page: int = 1, limit: int = 20) -> str:
    """List segments (chunks) of a document.

    Args:
        dataset_id: Dataset UUID.
        document_id: Document UUID.
        page: Page number.
        limit: Items per page.
    """
    with _client() as c:
        r = c.get(
            f"/datasets/{dataset_id}/documents/{document_id}/segments",
            params={"page": page, "limit": limit},
        )
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_dataset_indexing_status(dataset_id: str) -> str:
    """Get the indexing status of a dataset."""
    with _client() as c:
        r = c.get(f"/datasets/{dataset_id}/indexing-status")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def hit_testing(dataset_id: str, query: str) -> str:
    """Test knowledge base retrieval — find which chunks match a query.

    Args:
        dataset_id: Dataset UUID.
        query: The search query to test.
    """
    with _client() as c:
        r = c.post(f"/datasets/{dataset_id}/hit-testing", json={"query": query})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_dataset_related_apps(dataset_id: str) -> str:
    """Get applications that use this dataset."""
    with _client() as c:
        r = c.get(f"/datasets/{dataset_id}/related-apps")
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 7. MODEL PROVIDER MANAGEMENT
# ===========================================================================

@mcp.tool()
def list_model_providers() -> str:
    """List all configured model providers (OpenAI, Anthropic, Ollama, etc.)."""
    with _client() as c:
        r = c.get("/workspaces/current/model-providers")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_provider_models(provider: str) -> str:
    """List available models for a specific provider.

    Args:
        provider: Provider name (e.g. "openai", "anthropic", "ollama").
    """
    with _client() as c:
        r = c.get(f"/workspaces/current/model-providers/{provider}/models")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_default_model(model_type: str = "llm") -> str:
    """Get the current default model configuration.

    Args:
        model_type: "llm", "text-embedding", "rerank", "speech2text", "tts".
    """
    with _client() as c:
        r = c.get("/workspaces/current/default-model", params={"model_type": model_type})
        if r.status_code == 400:
            return _json({"error": "No default model set for this type.", "detail": r.json()})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def set_default_model(provider: str, model: str, model_type: str = "llm") -> str:
    """Set the default model for the workspace.

    Args:
        provider: Provider name (e.g. "openai").
        model: Model name (e.g. "gpt-4o").
        model_type: Model type — "llm", "text-embedding", "rerank", "speech2text", "tts".
    """
    with _client() as c:
        r = c.post("/workspaces/current/default-model", json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
        })
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 8. TOOL PROVIDER MANAGEMENT
# ===========================================================================

@mcp.tool()
def list_tool_providers() -> str:
    """List all available tool providers (builtin, API, workflow, MCP)."""
    with _client() as c:
        r = c.get("/workspaces/current/tool-providers")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def list_builtin_tools(provider: str) -> str:
    """List tools available from a builtin provider.

    Args:
        provider: Builtin provider name (e.g. "google", "wikipedia").
    """
    with _client() as c:
        r = c.get(f"/workspaces/current/tool-provider/builtin/{provider}/tools")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def list_workflow_tools() -> str:
    """List all workflow-as-tool definitions."""
    with _client() as c:
        r = c.get("/workspaces/current/tools/workflow")
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 9. ENVIRONMENT VARIABLES
# ===========================================================================

@mcp.tool()
def get_environment_variables(app_id: str) -> str:
    """Get workflow environment variables.

    Args:
        app_id: Application UUID.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflows/draft/environment-variables")
        if r.status_code == 404:
            return _json({"error": "No draft workflow found. Cannot read env vars.", "variables": []})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def get_conversation_variables(app_id: str) -> str:
    """Get workflow conversation variables.

    Args:
        app_id: Application UUID.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/workflows/draft/conversation-variables")
        if r.status_code == 404:
            return _json({"error": "No draft workflow found. Cannot read conversation vars.", "variables": []})
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 10. API KEY MANAGEMENT
# ===========================================================================

@mcp.tool()
def list_app_api_keys(app_id: str) -> str:
    """List API keys for an application."""
    with _client() as c:
        r = c.get(f"/apps/{app_id}/api-keys")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def create_app_api_key(app_id: str) -> str:
    """Create a new API key for an application."""
    with _client() as c:
        r = c.post(f"/apps/{app_id}/api-keys")
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def delete_app_api_key(app_id: str, api_key_id: str) -> str:
    """Delete an API key from an application.

    Args:
        app_id: Application UUID.
        api_key_id: API key ID to delete.
    """
    with _client() as c:
        r = c.delete(f"/apps/{app_id}/api-keys/{api_key_id}")
        r.raise_for_status()
        return _json({"result": "success", "message": f"API key {api_key_id} deleted."})


# ===========================================================================
# 11. TAGS
# ===========================================================================

@mcp.tool()
def list_tags(tag_type: str = "app") -> str:
    """List all tags.

    Args:
        tag_type: "app" or "knowledge".
    """
    with _client() as c:
        r = c.get("/tags", params={"type": tag_type})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def create_tag(name: str, tag_type: str = "app") -> str:
    """Create a new tag.

    Args:
        name: Tag name.
        tag_type: "app" or "knowledge".
    """
    with _client() as c:
        r = c.post("/tags", json={"name": name, "type": tag_type})
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 12. CONVERSATIONS & MESSAGES
# ===========================================================================

@mcp.tool()
def list_conversations(app_id: str, page: int = 1, limit: int = 20) -> str:
    """List conversations for a chat application.

    Args:
        app_id: Application UUID.
        page: Page number.
        limit: Items per page.
    """
    with _client() as c:
        r = c.get(f"/apps/{app_id}/chat-conversations", params={"page": page, "limit": limit})
        if r.status_code == 400:
            # Try completion conversations
            r = c.get(f"/apps/{app_id}/completion-conversations", params={"page": page, "limit": limit})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def list_messages(app_id: str, conversation_id: str | None = None, page: int = 1, limit: int = 20) -> str:
    """List chat messages for an application.

    Args:
        app_id: Application UUID.
        conversation_id: Optional conversation ID to filter.
        page: Page number.
        limit: Items per page.
    """
    params: dict[str, Any] = {"page": page, "limit": limit}
    if conversation_id:
        params["conversation_id"] = conversation_id
    with _client() as c:
        r = c.get(f"/apps/{app_id}/chat-messages", params=params)
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 13. SITE & API ACCESS CONTROL
# ===========================================================================

@mcp.tool()
def toggle_app_site(app_id: str, enable: bool) -> str:
    """Enable or disable web site access for an application.

    Args:
        app_id: Application UUID.
        enable: True to enable, False to disable.
    """
    with _client() as c:
        r = c.post(f"/apps/{app_id}/site-enable", json={"enable_site": enable})
        r.raise_for_status()
        return _json(r.json())


@mcp.tool()
def toggle_app_api(app_id: str, enable: bool) -> str:
    """Enable or disable API access for an application.

    Args:
        app_id: Application UUID.
        enable: True to enable, False to disable.
    """
    with _client() as c:
        r = c.post(f"/apps/{app_id}/api-enable", json={"enable_api": enable})
        r.raise_for_status()
        return _json(r.json())


# ===========================================================================
# 14. HIGH-LEVEL UTILITIES (MCP-side logic, not direct API calls)
# ===========================================================================

@mcp.tool()
def dsl_diff(yaml_a: str, yaml_b: str) -> str:
    """Compare two DSL YAML strings and show differences.

    Args:
        yaml_a: First YAML (e.g. current version).
        yaml_b: Second YAML (e.g. modified version).
    """
    lines_a = yaml_a.splitlines(keepends=True)
    lines_b = yaml_b.splitlines(keepends=True)
    diff = list(difflib.unified_diff(lines_a, lines_b, fromfile="before", tofile="after", lineterm=""))
    if not diff:
        return _json({"result": "identical", "message": "No differences found."})
    return "\n".join(diff)


@mcp.tool()
def batch_test(app_id: str, test_cases: list[dict[str, Any]]) -> str:
    """Run multiple test cases against a workflow and compare results.

    Args:
        app_id: Workflow application UUID.
        test_cases: List of dicts, each with "name" and "inputs" keys.
                    Example: [{"name": "happy path", "inputs": {"text": "hello"}},
                              {"name": "edge case", "inputs": {"text": ""}}]
    """
    results = []
    with _client() as c:
        for tc in test_cases:
            tc_name = tc.get("name", f"test_{len(results)+1}")
            tc_inputs = tc.get("inputs", {})
            final_data: dict[str, Any] = {}
            try:
                with c.stream(
                    "POST", f"/apps/{app_id}/workflows/draft/run",
                    json={"inputs": tc_inputs}, timeout=120,
                ) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line.startswith("data: "):
                            try:
                                event = json.loads(line[6:])
                                if event.get("event") == "workflow_finished":
                                    final_data = event.get("data", {})
                            except json.JSONDecodeError:
                                continue
                results.append({
                    "name": tc_name,
                    "status": final_data.get("status", "unknown"),
                    "outputs": final_data.get("outputs"),
                    "error": final_data.get("error"),
                    "elapsed_time": final_data.get("elapsed_time"),
                    "total_tokens": final_data.get("total_tokens"),
                })
            except Exception as e:
                results.append({"name": tc_name, "status": "error", "error": str(e)})

    passed = sum(1 for r in results if r["status"] == "succeeded")
    return _json({
        "summary": f"{passed}/{len(results)} passed",
        "results": results,
    })


@mcp.tool()
def health_check() -> str:
    """Check the health of all Dify apps — error rates, recent failures.

    Returns a summary of each app with its last run status.
    """
    report: list[dict[str, Any]] = []
    with _client() as c:
        # Get all apps
        r = c.get("/apps", params={"page": 1, "limit": 100, "mode": "all"})
        r.raise_for_status()
        apps = r.json().get("data", [])

        for app in apps:
            app_info: dict[str, Any] = {
                "id": app.get("id"),
                "name": app.get("name"),
                "mode": app.get("mode"),
            }
            # For workflow apps, check recent runs
            if app.get("mode") in ("workflow", "advanced-chat"):
                try:
                    r2 = c.get(f"/apps/{app['id']}/workflow-runs", params={"page": 1, "limit": 5})
                    if r2.status_code == 200:
                        runs = r2.json().get("data", [])
                        if runs:
                            statuses = [run.get("status") for run in runs]
                            app_info["recent_runs"] = len(runs)
                            app_info["recent_statuses"] = statuses
                            app_info["failure_rate"] = f"{statuses.count('failed')}/{len(statuses)}"
                        else:
                            app_info["recent_runs"] = 0
                except Exception:
                    app_info["recent_runs"] = "error"
            report.append(app_info)

    healthy = sum(1 for a in report if a.get("failure_rate", "0/0").startswith("0/"))
    return _json({
        "total_apps": len(report),
        "healthy": healthy,
        "apps": report,
    })


@mcp.tool()
def export_all_apps_dsl(output_dir: str = "./dify-exports") -> str:
    """Export all apps as YAML DSL files to a local directory for version control.

    Args:
        output_dir: Directory path to save YAML files. Created if not exists.
    """
    os.makedirs(output_dir, exist_ok=True)
    exported = []
    errors = []
    with _client() as c:
        r = c.get("/apps", params={"page": 1, "limit": 100, "mode": "all"})
        r.raise_for_status()
        apps = r.json().get("data", [])

        for app in apps:
            app_id = app["id"]
            app_name = app.get("name", app_id).replace("/", "_").replace(" ", "_")
            try:
                r2 = c.get(f"/apps/{app_id}/export", params={"include_secret": "false"})
                if r2.status_code == 200:
                    dsl = r2.json().get("data", "")
                    filepath = os.path.join(output_dir, f"{app_name}.yaml")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(dsl)
                    exported.append({"app": app.get("name"), "file": filepath})
                else:
                    errors.append({"app": app.get("name"), "error": f"HTTP {r2.status_code}"})
            except Exception as e:
                errors.append({"app": app.get("name"), "error": str(e)})

    return _json({"exported": len(exported), "errors": len(errors), "files": exported, "error_details": errors})


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
