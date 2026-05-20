from . import anthropic, bedrock, copilot, gemini, ollama, openai


_REGISTRY = {
    "bedrock": bedrock,
    "anthropic": anthropic,
    "openai": openai,
    "gemini": gemini,
    "copilot": copilot,
    "ollama": ollama,
}


def build_model(provider: str, model_id: str):
    mod = _REGISTRY.get(provider)
    if mod is None:
        raise RuntimeError(f"Unknown provider: {provider}")
    return mod.build_model(model_id)


def make_callback(provider: str):
    if provider == "ollama":
        return ollama.make_callback()
    return None


def setup(provider: str, _ask) -> dict:
    mod = _REGISTRY.get(provider)
    if mod is None:
        raise RuntimeError(f"Unknown provider: {provider}")
    return mod.setup(_ask)
