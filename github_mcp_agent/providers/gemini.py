import os

import questionary

MODELS = [
    ("gemini-2.0-flash", "gemini-2.0-flash", "fast, recommended"),
    ("gemini-1.5-pro", "gemini-1.5-pro", "most capable"),
    ("gemini-1.5-flash", "gemini-1.5-flash", "fast"),
]


def build_model(model_id: str):
    from strands.models.litellm import LiteLLMModel
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set. Run 'github-agent setup' to configure.")
    return LiteLLMModel(model_id=f"gemini/{model_id}")


def setup(_ask) -> dict:
    from rich.console import Console
    Console().print("  [dim]Get your key at: aistudio.google.com/apikey[/dim]")
    key = _ask(questionary.password, "Google AI Studio API key:")
    model_choices = [f"{name}  ({desc})" for _, name, desc in MODELS]
    model_display = _ask(questionary.select, "Model:", choices=model_choices)
    return {
        "GEMINI_API_KEY": key,
        "MODEL_ID": MODELS[model_choices.index(model_display)][0],
    }
