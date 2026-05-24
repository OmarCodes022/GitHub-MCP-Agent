import json
import time
import urllib.error
import urllib.parse
import urllib.request

import questionary

MODELS = [
    ("gpt-4o", "gpt-4o", "flagship"),
    ("gpt-4o-mini", "gpt-4o-mini", "fast, cheap"),
    ("claude-sonnet-4-5", "claude-sonnet-4-5", "Anthropic via Copilot"),
    ("o3-mini", "o3-mini", "reasoning"),
    ("gemini-1.5-pro", "gemini-1.5-pro", "Google via Copilot"),
]

_CLIENT_ID = "Iv1.b507a08c87ecfe98"


def _device_flow() -> str:
    """Run GitHub device flow with the Copilot OAuth client, return an access token."""
    from rich.console import Console
    console = Console()

    data = urllib.parse.urlencode({"client_id": _CLIENT_ID, "scope": "read:user"}).encode()
    req = urllib.request.Request(
        "https://github.com/login/device/code",
        data=data,
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        device = json.loads(r.read())

    console.print(f"\n  Open: [bold cyan]{device['verification_uri']}[/bold cyan]")
    console.print(f"  Code: [bold yellow]{device['user_code']}[/bold yellow]\n")

    interval = device.get("interval", 5)
    deadline = time.time() + device.get("expires_in", 900)

    while time.time() < deadline:
        time.sleep(interval)
        poll_data = urllib.parse.urlencode({
            "client_id": _CLIENT_ID,
            "device_code": device["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }).encode()
        poll_req = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=poll_data,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(poll_req) as r:
            result = json.loads(r.read())

        if "access_token" in result:
            return result["access_token"]
        error = result.get("error", "")
        if error == "slow_down":
            interval += 5
        elif error not in ("authorization_pending",):
            raise RuntimeError(f"Auth failed: {result.get('error_description', error)}")

    raise RuntimeError("Authentication timed out.")


def _get_copilot_token(oauth_token: str) -> str:
    """Exchange a Copilot OAuth token for a short-lived Copilot API token."""
    req = urllib.request.Request("https://api.github.com/copilot_internal/v2/token")
    req.add_header("Authorization", f"token {oauth_token}")
    req.add_header("Accept", "application/json")
    req.add_header("Editor-Version", "vscode/1.85.0")
    req.add_header("Editor-Plugin-Version", "copilot/1.138.0")
    req.add_header("User-Agent", "GithubCopilot/1.138.0")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())["token"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"Failed to get Copilot token (HTTP {e.code}).\n"
            "Make sure you have an active Copilot subscription."
        )


def build_model(model_id: str):
    import os
    from strands.models.litellm import LiteLLMModel
    oauth_token = os.environ.get("COPILOT_OAUTH_TOKEN")
    if not oauth_token:
        raise RuntimeError("Copilot token not set. Run 'github-agent provider' and pick GitHub Copilot.")
    token = _get_copilot_token(oauth_token)
    return LiteLLMModel(
        model_id=f"openai/{model_id}",
        params={
            "api_base": "https://api.githubcopilot.com",
            "api_key": token,
            "extra_headers": {
                "Editor-Version": "vscode/1.85.0",
                "Editor-Plugin-Version": "copilot/1.138.0",
                "User-Agent": "GithubCopilot/1.138.0",
                "Copilot-Integration-Id": "vscode-chat",
            },
        },
    )


def setup(_ask) -> dict:
    from rich.console import Console
    console = Console()
    console.print("  [dim]Requires an active Copilot subscription (student pack, individual, or business).[/dim]")
    console.print("  [dim]Opening browser to authenticate with GitHub Copilot...[/dim]\n")

    oauth_token = _device_flow()

    model_choices = [f"{name}  ({desc})" for _, name, desc in MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    model_id = MODELS[model_choices.index(model_display)][0]
    return {"COPILOT_OAUTH_TOKEN": oauth_token, "MODEL_ID": model_id}
