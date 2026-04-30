import os

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client


GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
AWS_REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

github_mcp_client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "-e",
                "GITHUB_PERSONAL_ACCESS_TOKEN",
                "ghcr.io/github/github-mcp-server",
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN,
            },
        )
    )
)

model = BedrockModel(
    model_id=MODEL_ID,
    region_name=AWS_REGION,
)

system_prompt = """
You are a GitHub project management assistant.

You help with:
- analyzing repositories
- reading files
- creating GitHub issues
- summarizing pull requests
- creating project roadmaps

Rules:
- Never delete repositories.
- Never change repository settings.
- Never create more than 5 issues at once unless clearly asked.
- Before creating issues, summarize what you are about to create.
- You are running in a terminal. Use plain text only. No markdown, no bold, no tables, no emojis, no bullet symbols.
"""

with github_mcp_client:
    print("Starting GitHub MCP server with Docker...")

    tools = github_mcp_client.list_tools_sync()

    print(f"Loaded {len(tools)} GitHub tools.")

    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )

    print("Agent ready. Type 'exit' to quit.")

    while True:
        prompt = input("\nYou > ")

        if prompt.lower() in ["exit", "quit"]:
            break

        print("\nAgent >")
        response = agent(prompt)