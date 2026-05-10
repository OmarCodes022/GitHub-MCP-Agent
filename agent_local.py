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


import json
import urllib.request
import urllib.error

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
AWS_REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

console = Console()

LOCAL_REPO_PATH = os.getcwd()

def _gql(query, variables={}):
    data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=data, method="POST")
    req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

@tool
def set_issue_priority(owner: str, repo: str, issue_number: int, priority: str) -> str:
    """Set the Priority field on a GitHub issue. priority: urgent, high, medium, or low."""
    p = priority.lower()
    if p not in ("urgent", "high", "medium", "low"):
        return "Error: priority must be urgent, high, medium, or low"
    try:
        lookup = _gql("""
            query($owner: String!, $repo: String!, $num: Int!) {
              repository(owner: $owner, name: $repo) { issue(number: $num) { id } }
              organization(login: $owner) {
                issueFields(first: 10) {
                  nodes { ... on IssueFieldSingleSelect { id name options { id name } } }
                }
              }
            }""", {"owner": owner, "repo": repo, "num": issue_number})
        if "errors" in lookup:
            return f"Error: {lookup['errors'][0]['message']}"
        issue_id = lookup["data"]["repository"]["issue"]["id"]
        pf = next((f for f in lookup["data"]["organization"]["issueFields"]["nodes"] if f.get("name") == "Priority"), None)
        if not pf:
            return "Priority field not found in org"
        opt = next((o for o in pf["options"] if o["name"].lower() == p), None)
        if not opt:
            return f"Option '{p}' not found"
        result = _gql("""
            mutation($i: ID!, $f: ID!, $o: ID!) {
              updateIssueFieldValue(input: {
                issueId: $i
                issueField: { fieldId: $f, singleSelectOptionId: $o }
              }) { clientMutationId }
            }""", {"i": issue_id, "f": pf["id"], "o": opt["id"]})
        if "errors" in result:
            return f"Error: {result['errors'][0]['message']}"
        return f"Priority set to '{p}' on {owner}/{repo}#{issue_number}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()}"
    except Exception as e:
        return f"Error: {e}"

@tool
def list_issues_with_priorities(owner: str, repo: str, state: str = "OPEN") -> str:
    """List issues with their priority AND description in one call. Use this instead of list_issues whenever priorities matter. state: OPEN, CLOSED, or ALL."""
    try:
        result = _gql("""
            query($owner: String!, $repo: String!, $state: [IssueState!]) {
              repository(owner: $owner, name: $repo) {
                issues(first: 100, states: $state, orderBy: {field: CREATED_AT, direction: DESC}) {
                  nodes {
                    number title body state
                    issueFieldValues(first: 5) {
                      nodes {
                        ... on IssueFieldSingleSelectValue {
                          name
                          field { ... on IssueFieldSingleSelect { name } }
                        }
                      }
                    }
                  }
                }
              }
            }""", {"owner": owner, "repo": repo, "state": [state] if state != "ALL" else ["OPEN", "CLOSED"]})
        if "errors" in result:
            return f"Error: {result['errors'][0]['message']}"
        lines = []
        for issue in result["data"]["repository"]["issues"]["nodes"]:
            priority = "not set"
            for fv in issue.get("issueFieldValues", {}).get("nodes", []):
                if fv.get("field", {}).get("name") == "Priority":
                    priority = fv.get("name", "not set").lower()
                    break
            body = (issue.get("body") or "").strip().replace("\n", " ")[:150]
            lines.append(f"#{issue['number']} [{issue['state']}] {issue['title']} | Priority: {priority} | {body}")
        return "\n".join(lines) or "No issues found"
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
        tools = [t for t in github_mcp_client.list_tools_sync() if t.tool_name != "list_issues"]

        console.print()
        console.print(Rule("[bold green]GitHub MCP Agent[/bold green]"))
        repo_label = f"[bold]{current_repo}[/bold]" if current_repo else "[dim]none detected[/dim]"
        local_tools = [set_issue_priority, list_issues_with_priorities, read_local_file, list_local_files]
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
