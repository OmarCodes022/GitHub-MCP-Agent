import os
from contextlib import contextmanager

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

from tools import detect_current_repo, local_tools



GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
AWS_REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _load_system_prompt():
    with open(os.path.join(os.path.dirname(__file__), "system_prompt.txt")) as f:
        prompt = f.read()
    repo = detect_current_repo()
    if repo != "No GitHub remote detected":
        prompt += f"\n\nThe user is currently working in the GitHub repository: {repo}. Default to this repository for all actions unless the user explicitly specifies another."
    return prompt, repo if repo != "No GitHub remote detected" else None


github_mcp_client = MCPClient(
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
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN},
        )
    )
)

model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)


@contextmanager
def create_agent():
    system_prompt, current_repo = _load_system_prompt()
    with github_mcp_client:
        mcp_tools = github_mcp_client.list_tools_sync()
        agent = Agent(
            model=model,
            tools=mcp_tools + local_tools,
            system_prompt=system_prompt,
        )
        yield agent, current_repo, len(mcp_tools) + len(local_tools)
