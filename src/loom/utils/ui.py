"""Terminal UI output utilities with Rich styling.

Provides semantic colored output functions for CLI applications using Rich.
Implements consistent branding and visual hierarchy throughout the Loom CLI.

The module uses a single shared Console instance with a pre-configured theme,
ensuring consistent styling across all CLI output.

Theme Colors:
- **success**: Bold green (✔ successful operations)
- **error**: Bold red (✘ errors, with optional tips)
- **warning**: Yellow (! warnings and cautions)
- **hint**: Dim italic (💡 helpful tips)
- **info**: Cyan (informational messages)
- **brand**: Bold magenta (🧵 headers and Loom branding)

Usage:
    from loom.utils.ui import print_success, print_error, print_header

    print_header("Building Agent")
    print_success("Agent created successfully")
    print_error("Failed to load config", tip="Check loom.toml syntax")
"""

from rich.console import Console
from rich.theme import Theme

# 1. Visual Identity (Brand Book)
LOOM_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "hint": "dim italic",
        "brand": "bold magenta",
        "panel.border": "magenta",
    }
)

# 2. Singleton Console instance for all LOOM CLI output
console = Console(theme=LOOM_THEME)


# 3. Semantic Output Helpers
def print_success(message: str):
    """Print a success message with green checkmark.

    Args:
        message: Message to display.

    Example:
        >>> print_success("Agent created successfully")
        ✔ Agent created successfully
    """
    console.print(f"[success]✔[/success] {message}")


def print_error(message: str, tip: str | None = None):
    """Print an error message with optional helpful tip.

    Args:
        message: Error description.
        tip: Optional helpful suggestion for resolving the error.

    Example:
        >>> print_error("Failed to load config", tip="Check loom.toml syntax")
        ✘ ERROR: Failed to load config
        💡 Tip: Check loom.toml syntax
    """
    console.print(f"\n[error]✘ ERROR:[/error] {message}")
    if tip:
        console.print(f"[hint]💡 Tip: {tip}[/hint]")


def print_warning(message: str):
    """Print a warning message in yellow.

    Args:
        message: Warning message to display.

    Example:
        >>> print_warning("Agent will be overwritten")
        ! Agent will be overwritten
    """
    console.print(f"[warning]![/warning] {message}")


def print_hint(message: str):
    """Print a helpful hint or tip in dim italic style.

    Args:
        message: Hint or tip message to display.

    Example:
        >>> print_hint("You can configure this in loom.toml")
        💡 You can configure this in loom.toml
    """
    console.print(f"[hint]💡 {message}[/hint]")


def print_header(title: str):
    """Print a section header with visual separator line.

    Creates a prominent section header with the Loom brand color and
    a visual separator line below it.

    Args:
        title: Section title (will be converted to uppercase).

    Example:
        >>> print_header("Building Agent")
        🧵 BUILDING AGENT
        ──────────────────
    """
    console.print(f"\n[brand]🧵 {title.upper()}[/brand]")
    console.print("[dim]" + "─" * (len(title) + 4) + "[/dim]")


def print_step(message: str):
    """Print a step in a multi-step process.

    Used to show progress through sequential operations.

    Args:
        message: Description of the current step.

    Example:
        >>> print_step("Loading configuration")
        → Loading configuration
    """
    console.print(f"[dim]→[/dim] {message}")
