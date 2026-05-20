import os

import questionary

MODELS = [
    ("claude-haiku-4-5-20251001", "claude-haiku-4-5", "fastest"),
    ("claude-sonnet-4-6", "claude-sonnet-4-6", "balanced"),
    ("claude-opus-4-7", "claude-opus-4-7", "most capable"),
]


def build_model(model_id: str):
    from strands.models.anthropic import AnthropicModel
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Run 'github-agent setup' to configure.")
    return AnthropicModel(model_id=model_id, max_tokens=8096)


def setup(_ask) -> dict:
    from rich.console import Console
    Console().print("  [dim]Get your key at: console.anthropic.com/settings/keys[/dim]")
    key = _ask(questionary.password, "Anthropic API key (sk-ant-...):")
    model_choices = [f"{name}  ({desc})" for _, name, desc in MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    return {
        "ANTHROPIC_API_KEY": key,
        "MODEL_ID": MODELS[model_choices.index(model_display)][0],
    }
