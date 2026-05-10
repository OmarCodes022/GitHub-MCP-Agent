import os
import re
import readline
import select
import subprocess
import sys

from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client


import urllib.request
import urllib.error
import json

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
AWS_REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

console = Console()

LOCAL_REPO_PATH = os.getcwd()

def _github_rest(path: str, method: str = "GET", body=None, params: dict = None):
    from urllib.parse import urlencode
    url = f"https://api.github.com{path}"
    if params:
        url += "?" + urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def _github_graphql(query: str, variables: dict):
    data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=data, method="POST")
    req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

@tool
def set_issue_priority(owner: str, repo: str, issue_number: int, priority: str) -> str:
    """Set the Priority issue field on a GitHub issue using GraphQL.
    owner: org login. repo: repository name. issue_number: issue number.
    priority: one of urgent, high, medium, low."""
    priority = priority.lower()
    if priority not in ("urgent", "high", "medium", "low"):
        return f"Error: priority must be urgent, high, medium, or low"
    try:
        # Get issue node_id
        issue = _github_rest(f"/repos/{owner}/{repo}/issues/{issue_number}")
        issue_node_id = issue["node_id"]

        # Get org issue fields to find Priority field and option node_ids
        fields_query = """
        {
          organization(login: "%s") {
            issueFields(first: 20) {
              nodes {
                ... on IssueFieldSingleSelect {
                  id name
                  options { id name }
                }
              }
            }
          }
        }
        """ % owner
        fields_result = _github_graphql(fields_query, {})
        if "errors" in fields_result:
            return f"Error fetching issue fields: {fields_result['errors']}"
        nodes = fields_result["data"]["organization"]["issueFields"]["nodes"]
        priority_field = next((n for n in nodes if n.get("name") == "Priority"), None)
        if not priority_field:
            return "Priority issue field not found in org"
        field_node_id = priority_field["id"]
        option = next((o for o in priority_field["options"] if o["name"].lower() == priority), None)
        if not option:
            return f"Option '{priority}' not found in Priority field"
        option_node_id = option["id"]

        # Set the field value
        mutation = """
        mutation($issueId: ID!, $fieldId: ID!, $optionId: ID!) {
          updateIssueFieldValue(input: {
            issueId: $issueId
            issueField: { fieldId: $fieldId, singleSelectOptionId: $optionId }
          }) { clientMutationId }
        }
        """
        result = _github_graphql(mutation, {
            "issueId": issue_node_id,
            "fieldId": field_node_id,
            "optionId": option_node_id,
        })
        if "errors" in result:
            return f"GraphQL error: {result['errors']}"
        return f"Priority set to '{priority}' on {owner}/{repo}#{issue_number}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()}"
    except Exception as e:
        return f"Error: {e}"

@tool
def read_local_file(path: str) -> str:
    """Read a file from the local repository. Path is relative to the repo root."""
    full_path = os.path.normpath(os.path.join(LOCAL_REPO_PATH, path))
    if not full_path.startswith(LOCAL_REPO_PATH):
        return "Error: path outside repo root"
    try:
        with open(full_path) as f:
            return f.read()
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def list_local_files(path: str = ".") -> str:
    """List files and directories in the local repository. Path is relative to the repo root."""
    full_path = os.path.normpath(os.path.join(LOCAL_REPO_PATH, path))
    if not full_path.startswith(LOCAL_REPO_PATH):
        return "Error: path outside repo root"
    try:
        entries = []
        for entry in sorted(os.scandir(full_path), key=lambda e: (not e.is_dir(), e.name)):
            prefix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{prefix}")
        return "\n".join(entries)
    except FileNotFoundError:
        return f"Directory not found: {path}"
    except Exception as e:
        return f"Error listing files: {e}"

def detect_current_repo():
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        ).decode().strip()
        match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

with open(os.path.join(os.path.dirname(__file__), "system_prompt.txt")) as f:
    system_prompt = f.read()

current_repo = detect_current_repo()
if current_repo:
    system_prompt += f"\n\nThe user is currently working in the GitHub repository: {current_repo}. Default to this repository for all actions unless the user explicitly specifies another."

github_mcp_client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "-e",
                "GITHUB_PERSONAL_ACCESS_TOKEN",
                "ghcr.io/github/github-mcp-server",
                "stdio",
                "--toolsets",
                "all",
                "--log-file",
                "/dev/null",
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN,
            },
        )
    )
)

model = BedrockModel(
    model_id=MODEL_ID,
    region_name=AWS_REGION,
)

try:
    with github_mcp_client:
        tools = github_mcp_client.list_tools_sync()

        console.print()
        console.print(Rule("[bold green]GitHub MCP Agent[/bold green]"))
        repo_label = f"[bold]{current_repo}[/bold]" if current_repo else "[dim]none detected[/dim]"
        local_tools = [set_issue_priority, read_local_file, list_local_files]
        total_tools = len(tools) + len(local_tools)
        console.print(f"  [dim]Loaded [bold]{total_tools}[/bold] tools  |  Repo: {repo_label}  |  Model: [bold]{MODEL_ID}[/bold]  |  Type 'exit' to quit[/dim]")
        console.print(Rule())
        console.print()

        agent = Agent(
            model=model,
            tools=tools + local_tools,
            system_prompt=system_prompt,
        )

        while True:
            try:
                user_input = input("\033[1;36m You > \033[0m")
                # collect additional lines if the user pastes multi-line content
                while select.select([sys.stdin], [], [], 0.05)[0]:
                    user_input += "\n" + sys.stdin.readline().rstrip("\n")
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input.strip():
                continue

            if user_input.strip().lower() in ["exit", "quit"]:
                break

            console.print()
            console.print(Text(" Agent", style="bold magenta"))
            console.print()

            try:
                agent(user_input)
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")

            console.print()

        console.print()
        console.print(Rule("[dim]Session ended[/dim]"))
        console.print()

except Exception as e:
    console.print(f"\n[bold red]Failed to start:[/bold red] {e}\n")
    sys.exit(1)
