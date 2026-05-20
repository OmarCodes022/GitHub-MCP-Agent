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

    model = providers.build_model(PROVIDER, MODEL_ID)
    system_prompt, current_repo = _load_system_prompt()

    with mcp_client:
        mcp_tools = mcp_client.list_tools_sync()
        agent_kwargs = dict(model=model, tools=mcp_tools + local_tools, system_prompt=system_prompt)
        cb = providers.make_callback(PROVIDER)
        if cb:
            agent_kwargs["callback_handler"] = cb
        agent = Agent(**agent_kwargs)
        yield agent, current_repo, len(mcp_tools) + len(local_tools)
