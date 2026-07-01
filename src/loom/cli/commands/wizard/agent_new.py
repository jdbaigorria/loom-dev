from typing import Any

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import EmptyInputValidator
from pydantic import TypeAdapter, ValidationError
from typer import Abort

from loom.config.profiles import get_profiles
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.models import ModelConfig
from loom.schemas.config.prompt import PromptConfig
from loom.schemas.config.retry import RetryConfig, RetryStrategyConfig
from loom.utils.ui import console

from ._completers import MODEL_IDS

model_adapter: TypeAdapter[ModelConfig] = TypeAdapter(ModelConfig)
retry_adapter: TypeAdapter[RetryStrategyConfig] = TypeAdapter(RetryStrategyConfig)
prompt_adapter: TypeAdapter[PromptConfig] = TypeAdapter(PromptConfig)


def ask_info(preset_name: str | None = None) -> dict:
    raw_data: dict[str, Any] = {}
    if preset_name:
        raw_data["name"] = preset_name
        console.print(f"🤖 [dim]Agent name:[/dim] [bold cyan]{preset_name}[/bold cyan]")
    else:
        raw_data["name"] = inquirer.text(
            message="🤖 Enter the name of the agent:",
            validate=EmptyInputValidator("Input should not be empty"),
            default="my_agent",
        ).execute()

    raw_data["name"] = (
        raw_data["name"].lower().replace("-", "_").replace(" ", "_")
    )  # normalize to snake_case
    raw_data.update(
        {
            "description": inquirer.text(
                message="💬 Enter the description of the agent:",
                multiline=True,
                default="My agent is a helpful assistant that can answer questions and help with tasks.",
            ).execute(),
            "output": inquirer.text(
                message="🤖 Enter the output of the agent:",
                default="",
            ).execute(),
        }
    )

    return raw_data


def ask_model_info() -> ModelConfig:
    """Pick a model profile, or define an inline (custom model_id) passthrough."""
    profiles = list(get_profiles().model)
    choice = inquirer.select(
        message="🤖 Select a model profile",
        choices=[*profiles, Choice("__custom__", name="custom (enter a model id)")],
        default=profiles[0] if profiles else "__custom__",
    ).execute()

    if choice != "__custom__":
        return str(choice)  # profile name

    model_id = inquirer.text(
        message="🤖 Enter the model ID:",
        completer=MODEL_IDS,
        multicolumn_complete=True,
        validate=EmptyInputValidator("Input should not be empty"),
    ).execute()
    raw = {
        "import_path": "strands.models.bedrock.BedrockModel",
        "params": {"model_id": model_id},
    }
    try:
        return model_adapter.validate_python(raw)
    except ValidationError as e:
        console.print("[bold red]✘ Model schema error:[/bold red]")
        for error in e.errors():
            console.print(
                f"  [yellow]→ {'.'.join(str(loc) for loc in error['loc'])}:[/yellow] {error['msg']}"
            )
        raise Abort()


def ask_retry() -> RetryStrategyConfig:
    """Pick a retry profile, or define an inline custom retry config."""
    profiles = list(get_profiles().retry)
    choice = inquirer.select(
        message="🤖 Select a retry profile",
        choices=[*profiles, Choice("__custom__", name="custom")],
        default=profiles[0] if profiles else "__custom__",
    ).execute()

    if choice != "__custom__":
        return str(choice)  # profile name

    raw: dict[str, Any] = {
        "max_attempts": int(
            inquirer.number(
                message="🤖 Max attempts:", default=5, min_allowed=1, max_allowed=100
            ).execute()
        ),
        "initial_delay": float(
            inquirer.number(
                message="🤖 Initial delay (s):", float_allowed=True, default=1, min_allowed=0
            ).execute()
        ),
        "max_delay": float(
            inquirer.number(
                message="🤖 Max delay (s):", float_allowed=True, default=60, min_allowed=0
            ).execute()
        ),
    }
    try:
        return RetryConfig(**raw)
    except ValidationError as e:
        console.print("[bold red]✘ Retry schema error:[/bold red]")
        for error in e.errors():
            console.print(
                f"  [yellow]→ {'.'.join(str(part) for part in error['loc'])}:[/yellow] {error['msg']}"
            )
        raise Abort()


def ask_system_prompt() -> PromptConfig:
    format_system_prompt = inquirer.select(
        message="🤖 Prompt mode:",
        choices=["file", "folder"],
    ).execute()

    if format_system_prompt == "file":
        prompt = "prompt.md"
    elif format_system_prompt == "folder":
        prompt = "prompts"

    try:
        return prompt_adapter.validate_python(prompt)
    except ValidationError as e:
        console.print("[bold red]✘ Prompt schema error:[/bold red]")
        for error in e.errors():
            console.print(
                f"  [yellow]→ {'.'.join(str(loc) for loc in error['loc'])}:[/yellow] {error['msg']}"
            )
        raise Abort()


def agent_context(preset_name: str | None = None) -> AgentConfig:
    if preset_name:
        info = ask_info(preset_name)
    else:
        info = ask_info()
    model = ask_model_info()
    retry = ask_retry()
    prompt = ask_system_prompt()
    return AgentConfig(**info, model=model, retry=retry, system_prompt=prompt)
