import os

import questionary

MODELS = [
    ("gpt-4o-mini", "gpt-4o-mini", "fast, cheap"),
    ("gpt-4o", "gpt-4o", "flagship"),
    ("gpt-4-turbo", "gpt-4-turbo", "legacy"),
]


def build_model(model_id: str):
    from strands.models.litellm import LiteLLMModel
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Run 'github-agent setup' to configure.")
    return LiteLLMModel(model_id=f"openai/{model_id}")


def setup(_ask) -> dict:
    from rich.console import Console
    Console().print("  [dim]Get your key at: platform.openai.com/api-keys[/dim]")
    key = _ask(questionary.password, "OpenAI API key (sk-...):")
    model_choices = [f"{name}  ({desc})" for _, name, desc in MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    return {
        "OPENAI_API_KEY": key,
        "MODEL_ID": MODELS[model_choices.index(model_display)][0],
    }
