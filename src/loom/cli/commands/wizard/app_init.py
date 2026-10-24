from dataclasses import dataclass
from typing import get_args

from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator
from pydantic import TypeAdapter, ValidationError
from typer import Abort

from loom.config.defaults import DEFAULT_REGION, DEFAULT_SESSION_PATH
from loom.schemas.config.app import AppConfig
from loom.schemas.config.conversations import ConversationConfig
from loom.schemas.config.sessions import SessionConfig
from loom.utils.ui import console

from ._completers import AWS_REGIONS


@dataclass
class InitContext:
    app: AppConfig
    workspace_name: str = "warp"
    project_name: str = "loom-project"
    project_description: str = "A project for the Loom framework"

    def to_template_context(self) -> dict:
        return {
            "app": {
                **self.app.model_dump(exclude_none=True),
                "workspace_name": self.workspace_name,
                "project_name": self.project_name,
                "project_description": self.project_description,
            }
        }


session_adapter: TypeAdapter[SessionConfig] = TypeAdapter(SessionConfig)
conversation_adapter: TypeAdapter[ConversationConfig] = TypeAdapter(ConversationConfig)


def ask_project_info(region: str | None = None) -> dict:
    project_name = inquirer.text(
        message="🤖 Project name:",
        default="loom-project",
        validate=EmptyInputValidator("Project name is required"),
    ).execute()

    project_description = inquirer.text(
        message="🤖 Project description:",
        default="A project for the Loom framework",
    ).execute()

    workspace_name = inquirer.text(
        message="🤖 Workspace folder name:",
        default="warp",
        validate=EmptyInputValidator("Workspace name is required"),
    ).execute()

    if not region:
        region = inquirer.text(
            message="🤖 AWS region:",
            completer=AWS_REGIONS,
            multicolumn_complete=True,
            default=DEFAULT_REGION,
            validate=EmptyInputValidator("Region is required"),
        ).execute()

    log_choices = list(get_args(AppConfig.model_fields["log_level"].annotation))
    log_level = inquirer.select(
        message="🤖 Select the log level:",
        choices=log_choices,
        default="INFO",
    ).execute()

    return {
        "project_name": project_name,
        "project_description": project_description,
        "workspace_name": workspace_name,
        "region": region,
        "log_level": log_level,
    }


def ask_app_session() -> SessionConfig:
    provider = inquirer.select(
        message="🤖 Enter the session provider:", choices=["file", "s3"]
    ).execute()

    if provider == "file":
        path = inquirer.text(
            message="🤖 Enter the file path:",
            default=DEFAULT_SESSION_PATH,
            validate=EmptyInputValidator("Input should not be empty"),
        ).execute()
        raw_data = {"provider": provider, "config": {"path": path}}
    else:  # Usamos else ya que select garantiza que sea uno de los dos
        bucket = inquirer.text(message="🤖 Enter the bucket name:").execute()
        prefix = inquirer.text(message="🤖 Enter the prefix:").execute()
        raw_data = {"provider": provider, "config": {"bucket": bucket, "prefix": prefix}}

    try:
        return session_adapter.validate_python(raw_data)
    except ValidationError as e:
        # Esto ayuda mucho durante el desarrollo de LOOM
        console.print(f"[bold red]✘ Session schema error:[/bold red] {e}")
        raise Abort()


def ask_app_conversation() -> ConversationConfig:
    strategy = inquirer.select(
        message="🤖 Select the conversation strategy:",
        choices=["Null", "sliding_window", "summarizing"],
    ).execute()

    if strategy == "Null":
        return conversation_adapter.validate_python({"strategy": "null"})

    config = {}

    if strategy == "sliding_window":
        config = {
            "window_size": int(inquirer.number(message="🤖 Window size:", default=10).execute()),
            "should_truncate_results": inquirer.confirm(
                message="🤖 Truncate results?", default=True
            ).execute(),
            "per_turn": inquirer.confirm(message="🤖 Per turn?", default=False).execute(),
        }

    elif strategy == "summarizing":
        # Parámetros base para summarizing
        config = {
            "summary_ratio": float(
                inquirer.number(
                    message="🤖 Summary ratio (0-1):",
                    default=0.3,
                    min_allowed=0.1,
                    max_allowed=0.9,
                    float_allowed=True,
                ).execute()
            ),
            "preserve_recent_messages": int(
                inquirer.number(
                    message="🤖 Preserve recent messages:", default=10, min_allowed=1
                ).execute()
            ),
        }

        type_sum = inquirer.select(
            message="🤖 Summarization type:", choices=["prompt", "agent"]
        ).execute()

        if type_sum == "prompt":
            mode = inquirer.select(
                message="🤖 Prompt mode:", choices=["default", "custom"]
            ).execute()
            config["summarization_system_prompt"] = (
                None
                if mode == "default"
                else inquirer.text(message="🤖 Custom prompt:", multiline=True).execute()
            )
        else:  # agent
            config["summarization_agent"] = {
                "model_id": inquirer.text(
                    message="🤖 Model ID:", default="anthropic.claude-haiku-5-5"
                ).execute(),
                "temperature": float(
                    inquirer.number(
                        message="🤖 Temperature:", default=0.1, min_allowed=0.0, max_allowed=1.0
                    ).execute()
                ),
                "max_tokens": int(
                    inquirer.number(
                        message="🤖 Max tokens:", default=1024, min_allowed=300, max_allowed=8192
                    ).execute()
                ),
            }

    try:
        raw_data = {"strategy": strategy, "config": config}
        return conversation_adapter.validate_python(raw_data)
    except ValidationError as e:
        console.print("[bold red]✘ Conversation schema error:[/bold red]")
        # Mostramos solo los errores relevantes para que el usuario entienda qué falló
        for error in e.errors():
            console.print(
                f"  [yellow]→ {'.'.join(str(loc) for loc in error['loc'])}:[/yellow] {error['msg']}"
            )
        raise Abort()


def app_context(region: str | None = None) -> InitContext:

    project = ask_project_info(region)
    session = ask_app_session()
    conversation = ask_app_conversation()

    app = AppConfig(
        region=project["region"],
        log_level=project["log_level"],
        session=session,
        conversation=conversation,
    )

    return InitContext(
        app=app,
        workspace_name=project["workspace_name"],
        project_name=project["project_name"],
        project_description=project["project_description"],
    )
