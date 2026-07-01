from uuid import uuid4

from rich.prompt import Prompt
from typer import Argument, Exit, Option, Typer

from loom.core.exceptions import AgentConfigError, AgentNotFoundError
from loom.core.loaders.app import resolve_env
from loom.dev import DevAgent, build_dev_agent, run_turn
from loom.schemas.context import LoomSession
from loom.utils.ui import console, print_error, print_hint, print_success

app: Typer = Typer()


def resolve_interrupts(dev: DevAgent, session: LoomSession, response):
    """Drive a human-in-the-loop exchange: prompt for each interrupt and resume.

    Loops until the agent finishes without pausing. Resume is native: the answers
    are fed back to the same live agent as interrupt-response content. Shared by
    ``run`` and ``dev``.
    """
    while response.interrupts:
        answers: dict[str, str] = {}
        for it in response.interrupts:
            detail = f" [dim]— {it.reason}[/dim]" if it.reason else ""
            console.print(
                f"[bold yellow]⏸ Agent needs input:[/bold yellow] {it.name or it.id}{detail}"
            )
            answers[it.id] = Prompt.ask("[bold blue]Your answer[/bold blue]")
        interrupt_content = [
            {"interruptResponse": {"interruptId": iid, "response": ans}}
            for iid, ans in answers.items()
        ]
        with console.status("[bold green]Resuming...[/bold green]"):
            response, _ = run_turn(dev, interrupt_content, session)
    return response


@app.callback(invoke_without_command=True)
def run_agent(
    name: str = Argument(..., help="Name of the agent to run"),
    message: str = Option(None, "--message", "-m", help="Single shot message to send to the agent"),
    env: str = Option(
        None, "--env", "-e", help="Environment profile (dev/prod). Overrides LOOM_ENV"
    ),
):
    active_env = env or resolve_env()
    print_hint(f"Booting up [white]{name}[/white] [dim](env: {active_env})[/dim]...")

    session = LoomSession(session_id=str(uuid4()), user_id="cli")
    try:
        dev = build_dev_agent(name, session, env=active_env)
    except AgentNotFoundError as e:
        print_error(str(e))
        raise Exit(1)
    except AgentConfigError as e:
        print_error(f"Invalid agent config: {e}")
        raise Exit(1)

    # The agent stays alive for the whole session (in-memory history); tear its
    # MCP connections down once, on the way out.
    try:
        # Single-shot mode: loom agent run my_agent -m "Hello"
        if message:
            print_hint(f"You: [white]{message}[/white]")
            try:
                with console.status("Agent is thinking..."):
                    response, _ = run_turn(dev, message, session)
                response = resolve_interrupts(dev, session, response)
                print_success(f"Agent: [white]{response.answer}[/white]")
            except Exception as e:
                print_error(f"Agent error: {e}")
                raise Exit(1)
            raise Exit(0)

        # Interactive mode
        print_hint(
            f"Starting interactive session with [white]{name}[/white].\n"
            "Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to stop."
        )

        while True:
            try:
                user_input = Prompt.ask("\n[bold blue]You[/bold blue]")

                if user_input.lower() in ["exit", "quit"]:
                    print_hint("Ending session. Bye!")
                    break

                if not user_input.strip():
                    continue

                with console.status("[bold green]Thinking...[/bold green]"):
                    response, _ = run_turn(dev, user_input, session)
                response = resolve_interrupts(dev, session, response)

                print_success(f"\n{name}: ")
                print_success(response.answer)

            except KeyboardInterrupt:
                print_hint("Session interrupted by user. Bye!")
                break
            except Exception as e:
                print_error(f"Agent error: {e}")
    finally:
        dev.agent.cleanup()
