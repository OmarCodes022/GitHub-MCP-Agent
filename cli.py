import readline
import select
import sys

from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from agent_local import MODEL_ID, create_agent

console = Console()


def run():
    try:
        with create_agent() as (agent, current_repo, total_tools):
            console.print()
            console.print(Rule("[bold green]GitHub MCP Agent[/bold green]"))
            repo_label = f"[bold]{current_repo}[/bold]" if current_repo else "[dim]none detected[/dim]"
            console.print(f"  [dim]Loaded [bold]{total_tools}[/bold] tools  |  Repo: {repo_label}  |  Model: [bold]{MODEL_ID}[/bold]  |  Type 'exit' to quit[/dim]")
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

    except Exception as e:
        console.print(f"\n[bold red]Failed to start:[/bold red] {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    run()
