import os
import subprocess

import questionary

POPULAR_MODELS = [
    "llama3.2",
    "llama3.1",
    "mistral",
    "gemma2",
    "phi3",
    "codellama",
    "deepseek-r1",
]


def build_model(model_id: str):
    from strands.models.litellm import LiteLLMModel
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return LiteLLMModel(model_id=f"ollama/{model_id}", params={"api_base": base_url})


def make_callback():
    import json as _json

    def callback(**kwargs):
        if "data" in kwargs:
            text = kwargs["data"]
            try:
                parsed = _json.loads(text)
                if isinstance(parsed, dict) and "text" in parsed:
                    text = parsed["text"]
            except Exception:
                pass
            print(text, end="", flush=True)

    return callback


def pick_model(_ask) -> str:
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    installed = [line.split()[0] for line in result.stdout.splitlines()[1:] if line.split()]
    choices = (installed if installed else POPULAR_MODELS) + ["other (type manually)"]
    choice = _ask(questionary.select, "Model:", choices=choices)
    if choice == "other (type manually)":
        return _ask(questionary.text, "Model name:")
    return choice


def setup(_ask) -> dict:
    from rich.console import Console
    console = Console()

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
            model = choice
    else:
        console.print("  [dim]No models installed yet. Pick one to pull:[/dim]")
        choices = POPULAR_MODELS + ["other (type manually)"]
        choice = _ask(questionary.select, "Model:", choices=choices)
        if choice == "other (type manually)":
            model = _ask(questionary.text, "Model name:")
        else:
            model = choice
        console.print(f"\n  Running [bold]ollama pull {model}[/bold]")
        subprocess.run(["ollama", "pull", model])

    base_url = _ask(questionary.text, "Ollama base URL:", default="http://localhost:11434")
    return {"MODEL_ID": model, "OLLAMA_BASE_URL": base_url}
