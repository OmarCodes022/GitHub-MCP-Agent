import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

import questionary
from rich.console import Console
from rich.rule import Rule

console = Console()
CONFIG_DIR = Path.home() / ".config" / "github-mcp-agent"
CONFIG_FILE = CONFIG_DIR / ".env"

BEDROCK_REGIONS = [
    ("us-east-1", "N. Virginia - recommended"),
    ("us-west-2", "Oregon"),
    ("eu-west-1", "Ireland"),
    ("eu-central-1", "Frankfurt"),
    ("eu-west-3", "Paris"),
    ("ap-northeast-1", "Tokyo"),
    ("ap-southeast-1", "Singapore"),
    ("ap-southeast-2", "Sydney"),
    ("ca-central-1", "Canada"),
    ("sa-east-1", "Sao Paulo"),
]

BEDROCK_MODELS = [
    ("us.anthropic.claude-haiku-4-5-20251001-v1:0", "claude-haiku-4-5", "fastest, cheapest"),
    ("us.anthropic.claude-sonnet-4-6", "claude-sonnet-4-6", "balanced"),
    ("us.anthropic.claude-opus-4-7", "claude-opus-4-7", "most capable"),
]

ANTHROPIC_MODELS = [
    ("claude-haiku-4-5-20251001", "claude-haiku-4-5", "fastest"),
    ("claude-sonnet-4-6", "claude-sonnet-4-6", "balanced"),
    ("claude-opus-4-7", "claude-opus-4-7", "most capable"),
]

OPENAI_MODELS = [
    ("gpt-4o-mini", "gpt-4o-mini", "fast, cheap"),
    ("gpt-4o", "gpt-4o", "flagship"),
    ("gpt-4-turbo", "gpt-4-turbo", "legacy"),
]

GEMINI_MODELS = [
    ("gemini-2.0-flash", "gemini-2.0-flash", "fast, recommended"),
    ("gemini-1.5-pro", "gemini-1.5-pro", "most capable"),
    ("gemini-1.5-flash", "gemini-1.5-flash", "fast"),
]

OLLAMA_POPULAR_MODELS = [
    "llama3.2",
    "llama3.1",
    "mistral",
    "gemma2",
    "phi3",
    "codellama",
    "deepseek-r1",
]


def _check(label: str, ok: bool, hint: str = ""):
    if ok:
        console.print(f"  [green]OK[/green]  {label}")
    else:
        console.print(f"  [red]FAIL[/red] {label}" + (f" — {hint}" if hint else ""))
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


def _list_aws_profiles() -> list[str]:
    creds = Path.home() / ".aws" / "credentials"
    config = Path.home() / ".aws" / "config"
    profiles = []
    for f in [creds, config]:
        if f.exists():
            for line in f.read_text().splitlines():
                if line.startswith("[") and line.endswith("]"):
                    name = line[1:-1].replace("profile ", "")
                    if name not in profiles:
                        profiles.append(name)
    return profiles


def _validate_aws_profile(profile: str) -> bool:
    env = os.environ.copy()
    env["AWS_PROFILE"] = profile
    return subprocess.run(["aws", "sts", "get-caller-identity"], capture_output=True, env=env).returncode == 0


def _setup_bedrock() -> dict:
    values = {}

    while True:
        cred_method = _ask(
            questionary.select,
            "AWS credentials:",
            choices=[
                "Use existing profile",
                "Enter access keys directly",
                "AWS SSO / browser login",
            ],
        )

        if cred_method == "Use existing profile":
            profiles = _list_aws_profiles()
            choices = profiles + ["other (type manually)"] if profiles else ["other (type manually)"]
            choice = _ask(questionary.select, "AWS profile:", choices=choices)
            if choice == "other (type manually)":
                profile = _ask(questionary.text, "Profile name:", default="default")
            else:
                profile = choice
            console.print("  Validating...", end=" ")
            if _validate_aws_profile(profile):
                console.print("[green]valid[/green]")
                values["AWS_PROFILE"] = profile
                break
            else:
                console.print("[red]invalid - check your AWS credentials[/red]")

        elif cred_method == "Enter access keys directly":
            values["AWS_ACCESS_KEY_ID"] = _ask(questionary.text, "AWS Access Key ID:")
            values["AWS_SECRET_ACCESS_KEY"] = _ask(questionary.password, "AWS Secret Access Key:")
            session_token = _ask(questionary.text, "AWS Session Token (leave blank if none):")
            if session_token:
                values["AWS_SESSION_TOKEN"] = session_token
            break

        elif cred_method == "AWS SSO / browser login":
            profiles = _list_aws_profiles()
            choices = profiles + ["other (type manually)"] if profiles else ["other (type manually)"]
            choice = _ask(questionary.select, "SSO profile to use:", choices=choices)
            if choice == "other (type manually)":
                profile = _ask(questionary.text, "Profile name:")
            else:
                profile = choice
            console.print(f"\n  Running [bold]aws sso login --profile {profile}[/bold]")
            result = subprocess.run(["aws", "sso", "login", "--profile", profile])
            if result.returncode == 0:
                values["AWS_PROFILE"] = profile
                break
            console.print("[red]SSO login failed - profile may not be configured for SSO.[/red]")
            console.print("[dim]  Run: aws configure sso --profile <name>[/dim]")
            console.print("[dim]  Or pick a different credential method below.[/dim]\n")

    region_choices = [f"{r}  ({label})" for r, label in BEDROCK_REGIONS]
    region_display = _ask(questionary.select, "AWS Region:", choices=region_choices)
    values["AWS_REGION"] = region_display.split()[0]

    model_choices = [f"{name}  ({desc})  ->  {mid}" for mid, name, desc in BEDROCK_MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    values["MODEL_ID"] = BEDROCK_MODELS[model_choices.index(model_display)][0]

    return values


def _setup_anthropic() -> dict:
    console.print("  [dim]Get your key at: console.anthropic.com/settings/keys[/dim]")
    key = _ask(questionary.password, "Anthropic API key (sk-ant-...):")
    model_choices = [f"{name}  ({desc})" for _, name, desc in ANTHROPIC_MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    return {
        "ANTHROPIC_API_KEY": key,
        "MODEL_ID": ANTHROPIC_MODELS[model_choices.index(model_display)][0],
    }


def _setup_openai() -> dict:
    console.print("  [dim]Get your key at: platform.openai.com/api-keys[/dim]")
    key = _ask(questionary.password, "OpenAI API key (sk-...):")
    model_choices = [f"{name}  ({desc})" for _, name, desc in OPENAI_MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    return {
        "OPENAI_API_KEY": key,
        "MODEL_ID": OPENAI_MODELS[model_choices.index(model_display)][0],
    }


def _setup_gemini() -> dict:
    console.print("  [dim]Get your key at: aistudio.google.com/apikey[/dim]")
    key = _ask(questionary.password, "Google AI Studio API key:")
    model_choices = [f"{name}  ({desc})" for _, name, desc in GEMINI_MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    return {
        "GEMINI_API_KEY": key,
        "MODEL_ID": GEMINI_MODELS[model_choices.index(model_display)][0],
    }


def _setup_ollama() -> dict:
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    installed = []
    if result.returncode == 0:
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                installed.append(parts[0])

    if installed:
        choices = installed + ["other (type manually)"]
        choice = _ask(questionary.select, "Model:", choices=choices)
        if choice == "other (type manually)":
            model = _ask(questionary.text, "Model name (e.g. llama3.2):")
        else:
            model = choice.split(":")[0]
    else:
        console.print("  [dim]No models installed yet. Pick one to pull:[/dim]")
        choices = OLLAMA_POPULAR_MODELS + ["other (type manually)"]
        choice = _ask(questionary.select, "Model:", choices=choices)
        if choice == "other (type manually)":
            model = _ask(questionary.text, "Model name:")
        else:
            model = choice
        console.print(f"\n  Running [bold]ollama pull {model}[/bold]")
        subprocess.run(["ollama", "pull", model])

    base_url = _ask(questionary.text, "Ollama base URL:", default="http://localhost:11434")
    return {"MODEL_ID": model, "OLLAMA_BASE_URL": base_url}


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

    provider = _ask(
        questionary.select,
        "AI provider:",
        choices=["AWS Bedrock", "Anthropic API", "OpenAI", "Google Gemini", "Local (Ollama)"],
    )

    if not _check_prerequisites(need_aws=provider == "AWS Bedrock"):
        console.print("\n[red]Fix the issues above before continuing.[/red]")
        sys.exit(1)

    console.print()

    provider_key = {"AWS Bedrock": "bedrock", "Anthropic API": "anthropic", "OpenAI": "openai", "Google Gemini": "gemini"}[provider]

    if provider == "AWS Bedrock":
        provider_values = _setup_bedrock()
    elif provider == "Anthropic API":
        provider_values = _setup_anthropic()
    elif provider == "OpenAI":
        provider_values = _setup_openai()
    else:
        provider_values = _setup_gemini()

    _write_config({"GITHUB_TOKEN": token, "PROVIDER": provider_key, **provider_values})
    console.print(f"\n  [dim]Config saved to {CONFIG_FILE}[/dim]")

    _pull_docker_image()

    console.print()
    console.print(Rule("[bold green]Setup complete[/bold green]"))
    console.print()
    console.print("  Run [bold cyan]github-agent[/bold cyan] to start.")
    console.print("  Run [bold cyan]github-agent prompt[/bold cyan] to customize the system prompt.")
    console.print()
