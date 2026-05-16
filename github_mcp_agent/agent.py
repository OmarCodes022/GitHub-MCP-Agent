import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

from github_mcp_agent.tools import detect_current_repo, local_tools

_config_dir = Path.home() / ".config" / "github-mcp-agent"
load_dotenv(_config_dir / ".env")
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
PROVIDER = os.getenv("PROVIDER", "bedrock")


def _build_model():
    if PROVIDER == "anthropic":
        from strands.models.anthropic import AnthropicModel
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Run 'github-agent setup' to configure.")
        return AnthropicModel(model_id=MODEL_ID, max_tokens=8096)

    if PROVIDER == "openai":
        from strands.models.litellm import LiteLLMModel
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set. Run 'github-agent setup' to configure.")
        return LiteLLMModel(model_id=f"openai/{MODEL_ID}")

    if PROVIDER == "gemini":
        from strands.models.litellm import LiteLLMModel
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not set. Run 'github-agent setup' to configure.")
        return LiteLLMModel(model_id=f"gemini/{MODEL_ID}")

    if PROVIDER == "ollama":
        from strands.models.litellm import LiteLLMModel
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return LiteLLMModel(model_id=f"ollama/{MODEL_ID}", params={"api_base": base_url})

    return BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)


def _load_system_prompt() -> tuple[str, str | None]:
    custom = _config_dir / "system_prompt.txt"
    if custom.exists():
        prompt = custom.read_text()
    else:
        from importlib.resources import files
        prompt = files("github_mcp_agent").joinpath("system_prompt.txt").read_text()

    repo = detect_current_repo()
    if repo != "No GitHub remote detected":
        prompt += f"\n\nThe user is currently working in the GitHub repository: {repo}. Default to this repository for all actions unless the user explicitly specifies another."
        return prompt, repo
    return prompt, None


def _make_ollama_callback():
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


@contextmanager
def create_agent():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Run 'github-agent setup' to configure."
        )

    mcp_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="docker",
                args=[
                    "run", "-i", "--rm",
                    "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                    "ghcr.io/github/github-mcp-server",
                    "stdio",
                    "--toolsets", "all",
                    "--log-file", "/dev/null",
                ],
                env={"GITHUB_PERSONAL_ACCESS_TOKEN": token},
            )
        )
    )

    model = _build_model()
    system_prompt, current_repo = _load_system_prompt()

    with mcp_client:
        mcp_tools = mcp_client.list_tools_sync()
        agent_kwargs = dict(model=model, tools=mcp_tools + local_tools, system_prompt=system_prompt)
        if PROVIDER == "ollama":
            agent_kwargs["callback_handler"] = _make_ollama_callback()
        agent = Agent(**agent_kwargs)
        yield agent, current_repo, len(mcp_tools) + len(local_tools)
