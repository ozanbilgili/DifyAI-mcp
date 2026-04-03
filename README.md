[**English**](README.md) | [Turkce](README_TR.md)

# Dify Management MCP Server

An MCP (Model Context Protocol) server for managing Dify AI workflows directly from the Claude Code terminal.

No need for Dify's visual interface — you can create, edit, test, and publish workflows directly with Claude Code.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Claude Code](https://claude.ai/claude-code) CLI
- A running [Dify](https://github.com/langgenius/dify) instance (via Docker Compose)

## Setup

### 1. Clone the repo

```bash
git clone <repo-url> dify-mcp-server
cd dify-mcp-server
```

### 2. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Enable Admin API Key in Dify

Add the following to Dify's `docker/.env` file:

```ini
ADMIN_API_KEY_ENABLE=true
ADMIN_API_KEY=<generate-a-strong-key>
```

To generate a key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Important:** Add these two lines inside the `x-shared-env` block in Dify's `docker/docker-compose.yaml` (otherwise the env variables won't be passed to the container):

```yaml
x-shared-env: &shared-api-worker-env
  # ... existing values ...
  ADMIN_API_KEY_ENABLE: ${ADMIN_API_KEY_ENABLE:-false}
  ADMIN_API_KEY: ${ADMIN_API_KEY:-}
```

Then restart the containers:

```bash
cd docker
docker compose down && docker compose up -d
```

### 4. Get your Workspace ID

After logging into Dify:

```bash
# First, log in (password must be base64 encoded)
B64PASS=$(echo -n "<your-password>" | base64)
curl -s -c /tmp/cookies.txt -X POST http://localhost/console/api/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"<email>\",\"password\":\"$B64PASS\"}"

# Get CSRF token
CSRF=$(grep csrf_token /tmp/cookies.txt | awk '{print $NF}')

# Fetch workspace list
curl -s -b /tmp/cookies.txt "http://localhost/console/api/workspaces" \
  -H "X-Csrf-Token: $CSRF"
```

The `"id"` value in the output is your Workspace ID.

### 5. Register the MCP server with Claude Code

Add the following to the `"mcpServers"` section in `~/.claude.json` (or project-level `settings.json`):

```json
{
  "mcpServers": {
    "dify-manager": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--project", "/FULL/PATH/TO/dify-mcp-server",
        "python", "/FULL/PATH/TO/dify-mcp-server/server.py"
      ],
      "env": {
        "DIFY_BASE_URL": "http://localhost",
        "DIFY_ADMIN_API_KEY": "<your-admin-api-key>",
        "DIFY_WORKSPACE_ID": "<your-workspace-id>"
      }
    }
  }
}
```

> Replace `/FULL/PATH/TO/dify-mcp-server` with the full path to the cloned directory.

### 6. Restart Claude Code

```bash
claude
```

## Usage

You can give natural language commands in the Claude Code terminal:

```
> List the apps in Dify
> Export the "Customer Support" app as YAML and save to workflow.yaml
> Add a Python node to this workflow that performs sentiment analysis
> Push the changes to Dify and test with the input "Hello, I was very frustrated!"
> Publish the draft
```

## Features

- **Dify-as-Code:** Export workflows as YAML, edit them, restore — version control with Git
- **One-command testing:** Run workflows or individual nodes in test mode, see results instantly
- **Batch testing:** Run multiple test cases at once, compare success rates
- **Knowledge Base management:** Create datasets, upload documents, test RAG retrieval
- **Model & Tool management:** List model providers and tools, set default model
- **Statistics & Logs:** Token cost, daily usage, response time, error rates
- **Health check:** Check the status of all apps at once
- **DSL comparison:** Compare two YAML versions with diff
- **Bulk export:** Export all apps to YAML files

## MCP Tools (52 Tools)

### App Management
| Tool | Description |
|---|---|
| `list_apps` | List all apps (with pagination + filtering) |
| `get_app_detail` | Get app details |
| `create_app` | Create a new empty app |
| `delete_app` | Delete an app |
| `copy_app` | Copy an existing app |

### DSL Export / Import
| Tool | Description |
|---|---|
| `get_app_dsl` | Export workflow as YAML DSL |
| `update_app_dsl` | Import/update YAML DSL to Dify |

### Workflow Management
| Tool | Description |
|---|---|
| `get_workflow_draft` | Get the draft graph structure (nodes, edges) |
| `publish_workflow` | Publish the draft as the active version |
| `list_workflow_versions` | List all published workflow versions |
| `restore_workflow_version` | Restore a previous version |
| `run_workflow_test` | Run the draft workflow in test mode |
| `run_single_node` | Test a single node |
| `stop_workflow_task` | Stop a running workflow |
| `get_default_block_configs` | Get default configurations by node type |

### Logs & Run History
| Tool | Description |
|---|---|
| `get_workflow_runs` | List workflow run history |
| `get_workflow_run_detail` | Get details of a specific run |
| `get_node_executions` | Get node-level execution details |
| `get_workflow_app_logs` | Get app logs |

### Statistics
| Tool | Description |
|---|---|
| `get_app_statistics` | Message, user, token, cost, response time statistics |
| `get_workflow_statistics` | Workflow-specific run and cost statistics |

### Knowledge Base
| Tool | Description |
|---|---|
| `list_datasets` | List all datasets |
| `create_dataset` | Create a new dataset |
| `get_dataset_detail` | Get dataset details |
| `delete_dataset` | Delete a dataset |
| `list_documents` | List documents in a dataset |
| `get_document_segments` | List document chunks |
| `get_dataset_indexing_status` | Show indexing status |
| `hit_testing` | RAG retrieval test — find chunks matching a query |
| `get_dataset_related_apps` | Show apps using a dataset |

### Model Provider Management
| Tool | Description |
|---|---|
| `list_model_providers` | List all model providers |
| `get_provider_models` | List a provider's models |
| `get_default_model` | Show the default model |
| `set_default_model` | Set the default model |

### Tool Provider Management
| Tool | Description |
|---|---|
| `list_tool_providers` | List all tool providers |
| `list_builtin_tools` | List a provider's tools |
| `list_workflow_tools` | List workflow-as-tool definitions |

### Environment Variables
| Tool | Description |
|---|---|
| `get_environment_variables` | Get workflow env vars |
| `get_conversation_variables` | Get conversation variables |

### API Key Management
| Tool | Description |
|---|---|
| `list_app_api_keys` | List app API keys |
| `create_app_api_key` | Create a new API key |
| `delete_app_api_key` | Delete an API key |

### Tags
| Tool | Description |
|---|---|
| `list_tags` | List all tags |
| `create_tag` | Create a new tag |

### Conversations & Messages
| Tool | Description |
|---|---|
| `list_conversations` | List chat conversations |
| `list_messages` | List messages |

### Access Control
| Tool | Description |
|---|---|
| `toggle_app_site` | Enable/disable web interface access |
| `toggle_app_api` | Enable/disable API access |

### High-Level Tools
| Tool | Description |
|---|---|
| `dsl_diff` | Compare two YAML DSLs, show differences |
| `batch_test` | Run multiple test cases in batch |
| `health_check` | Check status and error rates of all apps |
| `export_all_apps_dsl` | Bulk export all apps to YAML files |

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DIFY_BASE_URL` | No | `http://localhost` | Dify instance URL |
| `DIFY_ADMIN_API_KEY` | Yes | - | Dify Admin API key |
| `DIFY_WORKSPACE_ID` | Yes | - | Dify Workspace UUID |

## Architecture

```
Claude Code  <-->  MCP Server (stdio)  <-->  Dify Console API
                   (this project)              (localhost/console/api)
                                                     |
                                                Dify Platform
                                              (Docker Compose)
```

The MCP server connects to the Dify Console API with `Authorization: Bearer <ADMIN_API_KEY>` + `X-WORKSPACE-ID` headers. No cookies/CSRF required.

## Troubleshooting

**"ADMIN_API_KEY env var not found"**
- Check that the `env` block in `settings.json` is correct.

**"401 Unauthorized" / "Invalid token"**
- Make sure the `ADMIN_API_KEY` and `ADMIN_API_KEY_ENABLE` lines are under `x-shared-env` in `docker-compose.yaml`.
- Restart with `docker compose down && docker compose up -d`.
- Check the env inside the container: `docker compose exec api env | grep ADMIN`

**"CSRF token is missing"**
- The Admin API key is not properly configured. Review the steps above.

## License

MIT
