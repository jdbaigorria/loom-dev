"""
loom.core.loaders.prompt — Load the system prompt from various sources.

Implements the Strategy pattern to support three prompt origins:

- **Inline** (``RawTextStrategy``): text comes directly from the YAML.
- **File** (``FileStrategy``): path to a ``.md`` or ``.txt`` file.
- **Directory** (``DirectoryStrategy``): concatenates all ``.md``/``.txt``
  files in the directory in alphabetical order.

Unsupported sources in this version (S3, Bedrock ARN, URL) raise
``AgentConfigError`` with a helpful message.
"""

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path

from loom.adapters.strands import SystemContentBlock
from loom.schemas.config.prompt import PromptConfig
from loom.utils.loaders import load_file_content

from ..exceptions import AgentConfigError
from ..paths import build_workspace_paths

logger = logging.getLogger(__name__)


class PromptStrategy(ABC):
    """Base interface for the various prompt loading strategies."""

    @abstractmethod
    def load(self, source: str | Path) -> str:
        """Load the prompt from the given source.

        Args:
            source: Prompt origin (inline text, path to a file, or path to a directory).

        Returns:
            System prompt content as a string.
        """


class RawTextStrategy(PromptStrategy):
    """Load prompt from inline text (YAML value).

    Returns the text exactly as provided in YAML, with leading/trailing
    whitespace removed.
    """

    def load(self, source: str | Path) -> str:
        """Strip and return inline text.

        Args:
            source: Raw text from YAML.

        Returns:
            str: Stripped text ready for use as system prompt.
        """
        return str(source).strip()


class FileStrategy(PromptStrategy):
    """Load prompt from a single text file.

    Reads the content of a .md or .txt file and returns it as the prompt.
    """

    def load(self, source: str | Path) -> str:
        """Read file content.

        Args:
            source: Path to text file (.md or .txt).

        Returns:
            str: File content as prompt text.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        logger.debug("Loading prompt from file: '%s'", source)
        return load_file_content(Path(source))


class DirectoryStrategy(PromptStrategy):
    """Load prompt from multiple files in a directory.

    Reads all .md and .txt files from a directory in alphabetical order
    and concatenates them with newlines between files.
    """

    def load(self, source: str | Path) -> str:
        """Concatenate files from directory in alphabetical order.

        Collects all .md and .txt files in the directory (non-recursive),
        sorts them alphabetically, and concatenates with double-newline separators.

        Args:
            source: Path to directory containing prompt files.

        Returns:
            str: Concatenated content of all prompt files.

        Raises:
            AgentConfigError: If directory contains no valid .md or .txt files.
        """
        prompt_parts = []
        valid_exts = (".md", ".txt")
        source = Path(source)

        files = sorted(
            [f for f in source.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
        )

        if not files:
            raise AgentConfigError(
                f"No valid files found in directory: {source}",
                tip="Add at least one .md or .txt file to the directory.",
            )

        logger.debug("Loading prompt from directory '%s': %d file(s)", source, len(files))

        for file in files:
            content = load_file_content(file)
            if content.strip():
                prompt_parts.append(f"\n{content}")
        return "\n\n".join(prompt_parts)


def _looks_like_file_path(source: str) -> bool:
    """Return True if source resembles a file/directory path rather than inline text."""
    p = Path(source)
    return p.suffix.lower() in (".md", ".txt", ".rst") or "/" in source or "\\" in source


def _resolve_source(prompt_config: str, base_path: Path | None = None) -> str:
    """Load the system prompt using the appropriate strategy.

    Resolves the prompt source in the following order:
    1. Unsupported sources (S3 / Bedrock ARN / URL) → ``AgentConfigError``.
    2. Path that resolves to a file → ``FileStrategy``.
    3. Path that resolves to a directory → ``DirectoryStrategy``.
    4. Path that doesn't exist on disk but looks like a file (.md/.txt/path) → ``AgentConfigError``.
    5. Fallback: inline text → ``RawTextStrategy``.

    Args:
        prompt_config: Prompt source string from the agent YAML.
        base_path: Base directory to resolve relative paths from (e.g. the agent
            configuration directory). If ``None``, uses project root from
            ``build_workspace_paths().root``.

    Returns:
        System prompt content ready to pass to ``strands.Agent``.

    Raises:
        AgentConfigError: If the source uses S3, a Bedrock ARN, an HTTP/S URL,
            or the directory contains no valid files.
    """
    source = prompt_config

    if not source:
        return ""

    if source.startswith("s3://"):
        raise AgentConfigError(
            "S3 prompt loading is not yet supported in this version.",
            tip="Use a local file (e.g. config/prompt.md) or inline text instead.",
        )

    if source.startswith("arn:aws:bedrock:"):
        raise AgentConfigError(
            "Bedrock prompt loading is not yet supported in this version.",
            tip="Use a local file (e.g. config/prompt.md) or inline text instead.",
        )

    if source.startswith("http://") or source.startswith("https://"):
        raise AgentConfigError(
            "URL prompt loading is not yet supported in this version.",
            tip="Use a local file (e.g. config/prompt.md) or inline text instead.",
        )

    try:
        target_path = ((base_path or build_workspace_paths().root) / source).resolve()
    except Exception:
        logger.debug("Prompt source is inline text (could not resolve as path)")
        return RawTextStrategy().load(source)

    if target_path.is_file():
        return FileStrategy().load(target_path)

    if target_path.is_dir():
        return DirectoryStrategy().load(target_path)

    if _looks_like_file_path(source):
        raise AgentConfigError(
            f"Prompt file or directory '{source}' not found.",
            tip=f"Expected path: {target_path}. Check the path in your agent YAML.",
        )

    logger.debug("Prompt source is inline text: '%s...'", source[:40])
    return RawTextStrategy().load(source)


def get_prompt(
    prompt_config: PromptConfig,
    base_path: Path | None = None,
) -> list[SystemContentBlock]:
    """Load and construct system prompt with static text, caching, and dynamic context.

    Builds a list of SystemContentBlock objects representing the complete system
    prompt. Handles:

    1. **Static text** - Loaded from inline, file, or directory source
    2. **Cache point** - Optional Claude cache hint (added if cache=true)
    3. **Dynamic context** - Optional variable-interpolated text

    The base_path parameter allows resolving relative file paths relative to a
    specific directory (e.g., agent config dir) rather than workspace root.

    Args:
        prompt_config: PromptConfig with source (prompt field), optional cache flag,
            and optional context + variables for dynamic sections.
        base_path: Directory to resolve relative paths from. If None, uses workspace root.

    Returns:
        list[SystemContentBlock]: Blocks for Strands Agent system prompt:
            - Block 0: Static text (required)
            - Block 1: Cache point (if enabled)
            - Block 2+: Dynamic context blocks (if provided)

    Raises:
        AgentConfigError: If source uses unsupported schemes (S3, Bedrock ARN, HTTP/HTTPS)
            or the directory source has no valid files.

    Example:
        Static prompt from file::

            prompt_config = PromptConfig(prompt="prompt.md")
            blocks = get_prompt(prompt_config, base_path=agent_config_dir)

        Dynamic prompt with caching::

            config = PromptConfig(
                prompt="base.md",
                cache=True,
                context="context.md",
                variables={"model_name": "Claude Sonnet 5.5"}
            )
            blocks = get_prompt(config)
    """
    # When the source has hydrated the prompt, `prompt`/`context` are literal text
    # (no path guessing); otherwise resolve from inline text / file / directory.
    static_text = (
        prompt_config.prompt
        if prompt_config.is_resolved
        else _resolve_source(prompt_config.prompt, base_path)
    )

    if not static_text:
        raise AgentConfigError(
            "System prompt is empty.",
            tip="Set 'system_prompt' in your agent YAML to a file path or inline text. "
            "Sending requests without a system prompt wastes tokens and returns generic responses.",
        )

    blocks = [SystemContentBlock(text=static_text)]

    # Cache point always after the static block
    if prompt_config.cache:
        blocks.append(SystemContentBlock(cachePoint={"type": "default"}))

    # Dynamic section (if provided)
    if prompt_config.context:
        dynamic_text = (
            prompt_config.context
            if prompt_config.is_resolved
            else _resolve_source(prompt_config.context, base_path)
        )
        if prompt_config.variables:
            dynamic_text = dynamic_text.format_map(defaultdict(str, prompt_config.variables))
        blocks.append(SystemContentBlock(text=dynamic_text))

    return blocks


def hydrate_prompt(prompt_config: PromptConfig, base_path: Path | None = None) -> PromptConfig:
    """Resolve a prompt's file/dir sources to literal text (ConfigSource hydration).

    Returns a copy of ``prompt_config`` with ``prompt`` (and ``context``, if any)
    replaced by their resolved text and ``is_resolved=True``, so a later
    :func:`get_prompt` uses the text verbatim and never touches the filesystem.
    Inline text and already-resolved configs pass through unchanged in content.

    Args:
        prompt_config: The declarative prompt config (may reference files/dirs).
        base_path: Directory to resolve relative paths from (the agent config dir).

    Raises:
        AgentConfigError: If a source uses an unsupported scheme (S3/Bedrock/URL)
            or a referenced file/directory does not exist.
    """
    if prompt_config.is_resolved:
        return prompt_config

    static_text = _resolve_source(prompt_config.prompt, base_path)
    context_text = (
        _resolve_source(prompt_config.context, base_path) if prompt_config.context else None
    )
    return prompt_config.model_copy(
        update={"prompt": static_text, "context": context_text, "is_resolved": True}
    )
