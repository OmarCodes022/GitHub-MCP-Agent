import os

import questionary

MODELS = [
    ("gpt-4o", "gpt-4o", "flagship"),
    ("gpt-4o-mini", "gpt-4o-mini", "fast, cheap"),
    ("claude-sonnet-4-5", "claude-sonnet-4-5", "Anthropic via Copilot"),
    ("o3-mini", "o3-mini", "reasoning"),
    ("gemini-1.5-pro", "gemini-1.5-pro", "Google via Copilot"),
]


def build_model(model_id: str):
    from strands.models.litellm import LiteLLMModel
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set. Run 'github-agent setup' to configure.")
    return LiteLLMModel(
        model_id=f"openai/{model_id}",
        params={"api_base": "https://api.githubcopilot.com", "api_key": token},
    )


def setup(_ask) -> dict:
    from rich.console import Console
    console = Console()
    console.print("  [dim]Uses your GitHub token - no extra API key needed.[/dim]")
    console.print("  [dim]Requires an active Copilot subscription (student pack, individual, or business).[/dim]")
    model_choices = [f"{name}  ({desc})" for _, name, desc in MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    return {"MODEL_ID": MODELS[model_choices.index(model_display)][0]}
