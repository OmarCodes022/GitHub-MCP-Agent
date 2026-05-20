import os
import readline
import select
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

console = Console()

CONFIG_DIR = Path.home() / ".config" / "github-mcp-agent"


def _run_agent():
    from github_mcp_agent.agent import MODEL_ID, PROVIDER, create_agent
    try:
        with create_agent() as (agent, current_repo, total_tools):
            console.print()
            console.print(Rule("[bold green]GitHub MCP Agent[/bold green]"))
            repo_label = f"[bold]{current_repo}[/bold]" if current_repo else "[dim]none detected[/dim]"
            console.print(f"  [dim]Loaded [bold]{total_tools}[/bold] tools  |  Repo: {repo_label}  |  Provider: [bold]{PROVIDER}[/bold]  |  Model: [bold]{MODEL_ID}[/bold]  |  Type 'exit' to quit[/dim]")
            console.print(Rule())
            console.print()

            while True:
                try:
                    user_input = input("\033[1;36m You > \033[0m")
                    while select.select([sys.stdin], [], [], 0.05)[0]:
                        user_input += "\n" + sys.stdin.readline().rstrip("\n")
                except (KeyboardInterrupt, EOFError):
                    break

                if not user_input.strip():
                    continue
                if user_input.strip().lower() in ["exit", "quit"]:
                    break

                console.print()
                console.print(Text(" Agent", style="bold magenta"))
                console.print()

                try:
                    agent(user_input)
                except Exception as e:
                    console.print(f"[bold red]Error:[/bold red] {e}")

                console.print()

            console.print()
            console.print(Rule("[dim]Session ended[/dim]"))
            console.print()

    except RuntimeError as e:
        console.print(f"\n[bold red]{e}[/bold red]\n")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Failed to start:[/bold red] {e}\n")
        sys.exit(1)


def _open_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_file = CONFIG_DIR / ".env"
    if not config_file.exists():
        config_file.write_text(
            "GITHUB_TOKEN=\nAWS_PROFILE=default\nAWS_REGION=us-east-1\nMODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0\n"
        )
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(config_file)])


def _open_prompt():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    prompt_file = CONFIG_DIR / "system_prompt.txt"
    if not prompt_file.exists():
        from importlib.resources import files
        default = files("github_mcp_agent").joinpath("system_prompt.txt").read_text()
        prompt_file.write_text(default)
        console.print(f"  [dim]Created {prompt_file} with default prompt - edit to customize.[/dim]\n")
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(prompt_file)])


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """GitHub MCP Agent - talk to your repos in plain English."""
    if ctx.invoked_subcommand is None:
        _run_agent()


@cli.command()
def setup():
    """Run the interactive setup wizard."""
    from github_mcp_agent.setup_wizard import run
    run()


@cli.command()
def config():
    """Open the config file in $EDITOR."""
    _open_config()


@cli.command()
def prompt():
    """Open the system prompt file in $EDITOR."""
    _open_prompt()


def main():
    cli()


if __name__ == "__main__":
    main()
