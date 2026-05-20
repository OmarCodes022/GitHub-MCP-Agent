import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

from github_mcp_agent.tools import detect_current_repo, local_tools
from github_mcp_agent import providers


_config_dir = Path.home() / ".config" / "github-mcp-agent"
load_dotenv(_config_dir / ".env")
load_dotenv()

MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
PROVIDER = os.getenv("PROVIDER", "bedrock")
VERBOSE = os.getenv("VERBOSE", "").lower() in ("1", "true", "yes")


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


def _make_verbose_callback(provider: str):
    import json as _json
    is_ollama = provider == "ollama"

    def callback(**kwargs):
        if "current_tool_use" in kwargs:
            tool = kwargs["current_tool_use"]
            if tool.get("name"):
                print(f"\n  \033[2;36m> {tool['name']}\033[0m", flush=True)
        if "data" in kwargs:
            text = kwargs["data"]
            if is_ollama:
                try:
                    parsed = _json.loads(text)
                    if isinstance(parsed, dict) and "text" in parsed:
                        text = parsed["text"]
                except Exception:
                    pass
            print(text, end="", flush=True)

    return callback


@contextmanager
def create_agent(provider=None, model_id=None, verbose=False):
    _provider = provider or PROVIDER
    _model_id = model_id or MODEL_ID

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

    model = providers.build_model(_provider, _model_id)
    system_prompt, current_repo = _load_system_prompt()

    with mcp_client:
        mcp_tools = mcp_client.list_tools_sync()
        agent_kwargs = dict(model=model, tools=mcp_tools + local_tools, system_prompt=system_prompt)
        if verbose or VERBOSE:
            agent_kwargs["callback_handler"] = _make_verbose_callback(_provider)
        else:
            cb = providers.make_callback(_provider)
            if cb:
                agent_kwargs["callback_handler"] = cb
        agent = Agent(**agent_kwargs)
        yield agent, current_repo, len(mcp_tools) + len(local_tools)
