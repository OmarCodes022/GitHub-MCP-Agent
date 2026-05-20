import os
import subprocess
from pathlib import Path

import questionary

REGIONS = [
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

MODELS = [
    ("us.anthropic.claude-haiku-4-5-20251001-v1:0", "claude-haiku-4-5", "fastest, cheapest"),
    ("us.anthropic.claude-sonnet-4-6", "claude-sonnet-4-6", "balanced"),
    ("us.anthropic.claude-opus-4-7", "claude-opus-4-7", "most capable"),
]


def build_model(model_id: str):
    from strands.models import BedrockModel
    return BedrockModel(model_id=model_id, region_name=os.getenv("AWS_REGION", "us-east-1"))


def _list_aws_profiles() -> list[str]:
    profiles = []
    for f in [Path.home() / ".aws" / "credentials", Path.home() / ".aws" / "config"]:
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


def setup(_ask) -> dict:
    values = {}

    while True:
        cred_method = _ask(
            questionary.select,
            "AWS credentials:",
            choices=["Use existing profile", "Enter access keys directly", "AWS SSO / browser login"],
        )

        if cred_method == "Use existing profile":
            profiles = _list_aws_profiles()
            choices = profiles + ["other (type manually)"] if profiles else ["other (type manually)"]
            choice = _ask(questionary.select, "AWS profile:", choices=choices)
            if choice == "other (type manually)":
                profile = _ask(questionary.text, "Profile name:", default="default")
            else:
                profile = choice
            from rich.console import Console
            Console().print("  Validating...", end=" ")
            if _validate_aws_profile(profile):
                Console().print("[green]valid[/green]")
                values["AWS_PROFILE"] = profile
                break
            else:
                Console().print("[red]invalid - check your AWS credentials[/red]")

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
            from rich.console import Console
            console = Console()
            console.print(f"\n  Running [bold]aws sso login --profile {profile}[/bold]")
            result = subprocess.run(["aws", "sso", "login", "--profile", profile])
            if result.returncode == 0:
                values["AWS_PROFILE"] = profile
                break
            console.print("[red]SSO login failed - profile may not be configured for SSO.[/red]")
            console.print("[dim]  Run: aws configure sso --profile <name>[/dim]")
            console.print("[dim]  Or pick a different credential method below.[/dim]\n")

    region_choices = [f"{r}  ({label})" for r, label in REGIONS]
    region_display = _ask(questionary.select, "AWS Region:", choices=region_choices)
    values["AWS_REGION"] = region_display.split()[0]

    model_choices = [f"{name}  ({desc})  ->  {mid}" for mid, name, desc in MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    values["MODEL_ID"] = MODELS[model_choices.index(model_display)][0]

    return values
