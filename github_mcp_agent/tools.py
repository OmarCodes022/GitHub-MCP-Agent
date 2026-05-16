import json
import os
import re
import subprocess
import urllib.error
import urllib.request

from strands import tool

LOCAL_REPO_PATH = os.getcwd()


def _gql(query, variables={}):
    token = os.environ["GITHUB_TOKEN"]
    data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
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
def list_board_status(owner: str, project_number: int) -> str:
    """List all project board items grouped by their Status (Todo / In Progress / Done). Use this when the user asks about board status, what is in progress, or what is done. Never use projects_list for this — it overflows."""
    try:
        result = _gql("""
            query($owner: String!, $num: Int!) {
              organization(login: $owner) {
                projectV2(number: $num) {
                  items(first: 100) {
                    nodes {
                      content {
                        ... on Issue { number title state }
                      }
                      fieldValues(first: 10) {
                        nodes {
                          ... on ProjectV2ItemFieldSingleSelectValue {
                            name
                            field { ... on ProjectV2SingleSelectField { name } }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }""", {"owner": owner, "num": project_number})
        if "errors" in result:
            return f"Error: {result['errors'][0]['message']}"
        buckets: dict = {}
        for item in result["data"]["organization"]["projectV2"]["items"]["nodes"]:
            content = item.get("content") or {}
            if not content.get("number"):
                continue
            number = content["number"]
            title = content.get("title", "")
            status = "No Status"
            for fv in item.get("fieldValues", {}).get("nodes", []):
                if fv.get("field", {}).get("name") == "Status":
                    status = fv.get("name", "No Status")
                    break
            buckets.setdefault(status, []).append(f"  #{number} {title}")
        lines = []
        for status, items in buckets.items():
            lines.append(f"{status} ({len(items)}):")
            lines.extend(items)
            lines.append("")
        return "\n".join(lines) or "No items found"
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


@tool
def detect_current_repo() -> str:
    """Detect the GitHub repository the user is currently working in, based on the local git remote origin URL."""
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
    return "No GitHub remote detected"


local_tools = [
    set_issue_priority,
    list_issues_with_priorities,
    list_board_status,
    detect_current_repo,
    read_local_file,
    list_local_files,
]
