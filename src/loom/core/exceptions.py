from dataclasses import dataclass


class LoomError(Exception):
    """Base class for all Loom errors.

    Allows catching any framework error with a single except clause.
    """

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message)
        self.tip = tip


# --- Project Error Family ---


class ProjectError(LoomError):
    """Base class for errors related to project structure."""

    pass


class ProjectNotInitializedError(ProjectError):
    """Raised when the workspace directory or loom.toml does not exist."""

    def __init__(self, tip: str = "Run 'loom init' to initialize the project."):
        super().__init__("The project is not initialized.", tip=tip)


class ProjectAlreadyInitializedError(ProjectError):
    """Raised when attempting to initialize a directory that already has a project."""

    def __init__(self, tip: str = "Use --force to reinitialize: loom init --force"):
        super().__init__("A project already exists in this directory.", tip=tip)


# --- Agent Error Family ---


class AgentError(LoomError):
    """Base class for errors related to agents."""

    pass


class AgentNotFoundError(AgentError):
    """Raised when an agent that does not exist on disk is requested."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = f"Agent '{name}' not found." if name else "Agent not found."
        super().__init__(msg, tip=tip or "Check available agents with: loom agent list")


class NoAgentsFoundError(AgentError):
    """Raised when the agents directory exists but contains no agents."""

    def __init__(self, tip: str = "Create your first agent with: loom agent new <name>"):
        super().__init__("No agents found in the workspace.", tip=tip)


class AgentConfigError(AgentError):
    """Raised when the agent YAML is malformed or a required field is missing."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


class AgentAlreadyExistsError(AgentError):
    """Raised when attempting to create an agent that already exists."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = f"Agent '{name}' already exists." if name else "Agent already exists."
        super().__init__(
            msg,
            tip=tip
            or "Use a different name or remove the existing agent with: loom agent remove <name>",
        )


class AgentInstanceError(AgentError):
    """Raised when agent.py does not expose a valid 'agent' variable."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = (
            f"No 'agent' instance found in '{name}/agent.py'."
            if name
            else "No 'agent' instance found in agent.py."
        )
        super().__init__(msg, tip=tip or "Ensure agent.py defines a variable named 'agent'.")


# --- Evals Error Family ---


class EvalsError(LoomError):
    """Base class for errors related to evaluations."""

    pass


class EvalsNotFoundError(EvalsError):
    """Raised when no evals.yml file exists for an agent."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = f"No evals found for agent '{name}'." if name else "Evals not found."
        super().__init__(
            msg,
            tip=tip or f"Create a evals.yml file in warp/agents/{name}/evals/",
        )


class EvalsAlreadyExistsError(EvalsError):
    """Raised when an evals.yml file already exists for the agent."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = f"Evals already exist for agent '{name}'." if name else "Evals already exist."
        super().__init__(
            msg,
            tip=tip or "Remove the existing evals.yml or edit it directly.",
        )


class EvalsRunError(EvalsError):
    """Raised when the evaluation execution fails."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


# --- Workflow Error Family ---


class WorkflowError(LoomError):
    """Base class for errors related to multi-agent workflows."""

    pass


class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow that does not exist on disk is requested."""

    def __init__(self, name: str = "", tip: str | None = None):
        msg = f"Workflow '{name}' not found." if name else "Workflow not found."
        super().__init__(msg, tip=tip or "Check available workflows with: loom workflow list")


class NoWorkflowsFoundError(WorkflowError):
    """Raised when the workflows directory exists but contains no workflows."""

    def __init__(self, tip: str = "Create one under warp/workflows/<name>.yml"):
        super().__init__("No workflows found in the workspace.", tip=tip)


class WorkflowConfigError(WorkflowError):
    """Raised when a workflow YAML is malformed, references a missing agent, or the
    installed Strands version lacks the required multi-agent primitive."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


class TargetResolutionError(LoomError):
    """Raised when a name cannot be resolved to a single agent or workflow.

    Used by the polymorphic ``loom.invoke``: the name exists nowhere, or it
    exists as **both** an agent and a workflow and no ``kind`` was given to
    disambiguate.
    """

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


class ToolLoadError(AgentError):
    """Raised when a tool cannot be loaded (not found, params without a class, or missing tool_spec)."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


class ToolSelectionError(AgentError):
    """Raised when a requested tool subset references a tool not in the catalog.

    ``build()`` accepts a ``tools=`` subset to activate per call (e.g. Weave
    narrowing the catalog by permission/phase). The rule is *narrow, don't
    invent*: every requested name must exist in the agent's declared tools.
    """

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


class HookLoadError(AgentError):
    """Raised when a hook cannot be loaded (not found, not importable, or no valid class)."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


class ModelLoadError(AgentError):
    """Raised when a model cannot be loaded (not found, not importable, or no valid class)."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


class OutputLoadError(AgentError):
    """Raised when an output class cannot be loaded (not found, not importable, or no valid class)."""

    def __init__(self, message: str, tip: str | None = None):
        super().__init__(message, tip=tip)


# --- Validation ---


@dataclass
class ValidationResult:
    """Result of an individual validation check.

    Attributes:
        ok: ``True`` if the check passed, ``False`` if it failed.
        message: Description of the check result.
        tip: Corrective action suggestion (only when ``ok=False``).
    """

    ok: bool
    message: str
    tip: str | None = None
