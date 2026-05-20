import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

import questionary
from rich.console import Console
from rich.rule import Rule

from github_mcp_agent import providers

console = Console()
CONFIG_DIR = Path.home() / ".config" / "github-mcp-agent"
CONFIG_FILE = CONFIG_DIR / ".env"


def _check(label: str, ok: bool, hint: str = ""):
    if ok:
        console.print(f"  [green]OK[/green]  {label}")
    else:
        console.print(f"  [red]FAIL[/red] {label}" + (f" - {hint}" if hint else ""))
    return ok


def _check_prerequisites(provider: str = "bedrock") -> bool:
    console.print("\n[bold]Checking prerequisites...[/bold]")
    ok = True
    py = sys.version_info >= (3, 10)
    ok &= _check("Python >= 3.10", py, f"found {sys.version.split()[0]}")
    docker = subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    ok &= _check("Docker installed and running", docker, "install Docker from docker.com")
    if provider == "bedrock":
        aws = subprocess.run(["aws", "--version"], capture_output=True).returncode == 0
        ok &= _check("AWS CLI installed", aws, "install from aws.amazon.com/cli")
    if provider == "ollama":
        ollama_ok = subprocess.run(["ollama", "list"], capture_output=True).returncode == 0
        ok &= _check("Ollama installed and running", ollama_ok, "install from ollama.com then run: ollama serve")
    return ok


def _ask(fn, *args, **kwargs):
    try:
        val = fn(*args, **kwargs).ask()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Setup cancelled.[/yellow]")
        sys.exit(0)
    if val is None:
        console.print("\n[yellow]Setup cancelled.[/yellow]")
        sys.exit(0)
    return val


def _validate_github_token(token: str) -> bool:
    req = urllib.request.Request("https://api.github.com/user")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "github-mcp-agent")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False


def _pull_docker_image():
    console.print("\n[bold]Pulling GitHub MCP Docker image...[/bold]")
    subprocess.run(["docker", "pull", "ghcr.io/github/github-mcp-server"], check=False)


def _write_config(values: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    existing.update({k: v for k, v in values.items() if v})
    lines = [f"{k}={v}" for k, v in existing.items()]
    CONFIG_FILE.write_text("\n".join(lines) + "\n")


def run():
    console.print()
    console.print(Rule("[bold green]GitHub MCP Agent - Setup[/bold green]"))

    console.print()
    console.print("  [dim]Create a token at: github.com/settings/tokens[/dim]")
    console.print("  [dim]Required scopes: repo, read:org, project[/dim]")
    token = _ask(questionary.password, "GitHub Personal Access Token:")
    if token:
        console.print("  Validating...", end=" ")
        if _validate_github_token(token):
            console.print("[green]valid[/green]")
        else:
            console.print("[red]invalid - check the token and scopes[/red]")
            sys.exit(1)

    console.print()

    provider_display = _ask(
        questionary.select,
        "AI provider:",
        choices=["AWS Bedrock", "Anthropic API", "OpenAI", "Google Gemini", "GitHub Copilot", "Local (Ollama)"],
    )

    provider_key = {
        "AWS Bedrock": "bedrock",
        "Anthropic API": "anthropic",
        "OpenAI": "openai",
        "Google Gemini": "gemini",
        "GitHub Copilot": "copilot",
        "Local (Ollama)": "ollama",
    }[provider_display]

    if not _check_prerequisites(provider=provider_key):
        console.print("\n[red]Fix the issues above before continuing.[/red]")
        sys.exit(1)

    console.print()

    provider_values = providers.setup(provider_key, _ask)

    _write_config({"GITHUB_TOKEN": token, "PROVIDER": provider_key, **provider_values})
    console.print(f"\n  [dim]Config saved to {CONFIG_FILE}[/dim]")

    _pull_docker_image()

    console.print()
    console.print(Rule("[bold green]Setup complete[/bold green]"))
    console.print()
    console.print("  Run [bold cyan]github-agent[/bold cyan] to start.")
    console.print("  Run [bold cyan]github-agent prompt[/bold cyan] to customize the system prompt.")
    console.print()
