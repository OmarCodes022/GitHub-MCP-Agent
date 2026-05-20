# GitHub MCP Agent

Talk to your GitHub repos, issues, and project boards in plain English from your terminal.

```
You > list open issues in my raytracer repo
You > set priority of issue #42 to urgent
You > what's in progress on the project board?
You > which issues are assigned to maryam?
```

---

## Install

```bash
pip install github-mcp-agent
```

Or with uv:

```bash
uv tool install github-mcp-agent
```

---

## Setup

```bash
github-agent setup
```

Interactive wizard:

1. GitHub token (validated immediately)
2. AI provider — choose one:
   - **AWS Bedrock** — existing profile, access keys, or SSO
   - **Anthropic API** — API key from console.anthropic.com
   - **OpenAI** — API key from platform.openai.com
   - **Google Gemini** — API key from aistudio.google.com
   - **GitHub Copilot** — uses your GitHub token, requires a Copilot subscription
   - **Local (Ollama)** — picks from your installed models, no API key needed
3. Model selection (scrollable menu)
4. Pulls the GitHub MCP Docker image

Config saved to `~/.config/github-mcp-agent/.env`.

---

## Usage

```bash
github-agent            # start the agent
github-agent setup      # full setup wizard
github-agent provider   # switch AI provider and model
github-agent model      # switch model within current provider
github-agent token      # update GitHub token
github-agent config     # edit config file in $EDITOR
github-agent prompt     # customize the system prompt in $EDITOR
github-agent -v         # start with verbose tool output
```

---

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| Docker | Must be running — used for the GitHub MCP server |
| GitHub token | Scopes: `repo`, `read:org`, `project` — [github.com/settings/tokens](https://github.com/settings/tokens) |
| Provider credentials | See setup wizard |

**For AWS Bedrock:** enable Claude model access in the [Bedrock console](https://console.aws.amazon.com/bedrock) under Model access.

**For Ollama:** install from [ollama.com](https://ollama.com), run `ollama serve`. Models with good tool-calling support: `qwen2.5`, `llama3.1`, `mistral`.

**For GitHub Copilot:** requires an active Copilot subscription (student pack, individual, or business).

---

## How it works

```
You (terminal)
    │
    ▼
github-agent (CLI)
    │
    ├── AI model (Bedrock / Anthropic / OpenAI / Gemini / Copilot / Ollama)
    │
    └── GitHub MCP Server (Docker)
            │
            └── GitHub API
```

Uses the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) with the [GitHub MCP server](https://github.com/github/github-mcp-server).

---

## Troubleshooting

**`GITHUB_TOKEN` not set** — run `github-agent setup`

**Docker not running** — start Docker Desktop or `sudo systemctl start docker`

**Bedrock access denied** — check IAM permissions and model access in your region

**Ollama model not found** — run `ollama list` to confirm the model name, re-run `github-agent model`

**`No module named github_mcp_agent`** — reinstall with `uv tool install .` from the project directory
