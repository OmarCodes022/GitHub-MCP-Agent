# GitHub MCP Agent

A GitHub project management AI agent powered by AWS Bedrock and the Model Context Protocol. Talk to your GitHub repos, issues, and project boards in plain English from your terminal.

```
You > list open issues in my raytracer repo
You > set priority of issue #42 to urgent
You > what's in progress on the project board?
You > which issues are assigned to maryam?
```

---

## Install

**Recommended — uv (isolated, global command):**
```bash
git clone https://github.com/OmarCodes022/GitHub-MCP-Agent
cd GitHub-MCP-Agent
uv tool install .
```

**Or pip:**
```bash
git clone https://github.com/OmarCodes022/GitHub-MCP-Agent
cd GitHub-MCP-Agent
pip install .
```

---

## Setup

Run the interactive setup wizard once after installing:

```bash
github-agent setup
```

The wizard will:
- Check that Docker and the AWS CLI are installed
- Ask for your GitHub token and validate it
- Let you pick your AWS profile and validate credentials
- Pull the GitHub MCP Docker image
- Save your config to `~/.config/github-mcp-agent/.env`

---

## Usage

```bash
github-agent          # start the agent
github-agent setup    # re-run setup (change credentials, region, model)
github-agent config   # edit config file directly in $EDITOR
github-agent prompt   # customize the system prompt in $EDITOR
```

---

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| Docker | Must be running — used to run the GitHub MCP server |
| AWS account | Bedrock must be enabled in your region |
| GitHub token | Scopes: `repo`, `read:org`, `project` — create at [github.com/settings/tokens](https://github.com/settings/tokens) |

### Enable AWS Bedrock

1. Go to the [AWS Bedrock console](https://console.aws.amazon.com/bedrock)
2. Navigate to **Model access**
3. Request access to **Claude Haiku** (Anthropic)

### Get a GitHub token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Generate a new token (classic)
3. Select scopes: `repo`, `read:org`, `project`

---

## Configuration

Config is stored at `~/.config/github-mcp-agent/.env`:

```env
GITHUB_TOKEN=ghp_...
AWS_PROFILE=default
AWS_REGION=us-east-1
MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
```

Edit it directly with `github-agent config`.

### Custom system prompt

The agent ships with a built-in system prompt tuned for GitHub project management. To override it:

```bash
github-agent prompt
```

This opens `~/.config/github-mcp-agent/system_prompt.txt` in your editor. The file is pre-filled with the default — edit and save. Delete the file to revert to the default.

---

## How it works

```
You (terminal)
    │
    ▼
github-agent (CLI)
    │
    ├── AWS Bedrock (Claude Haiku via Strands Agents SDK)
    │
    └── GitHub MCP Server (Docker)
            │
            └── GitHub API
```

The agent uses the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) to connect Claude on Bedrock with the [GitHub MCP server](https://github.com/github/github-mcp-server), giving the model direct access to GitHub's API as tools. Custom tools handle GitHub Projects v2 priority fields and project board status.

---

## Troubleshooting

**`GITHUB_TOKEN` not set** — run `github-agent setup` or `github-agent config`

**Docker not running** — start Docker Desktop or `sudo systemctl start docker`

**Bedrock access denied** — check IAM permissions and that Claude Haiku is enabled in your region

**`No module named github_mcp_agent`** — reinstall with `uv tool install github-mcp-agent` or `pip install github-mcp-agent`
