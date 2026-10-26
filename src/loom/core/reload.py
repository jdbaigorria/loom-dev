"""
loom.core.reload — Invalidate Loom's on-disk config/file caches.

Loom memoizes parsed YAML, file content, and validated config objects with
``functools.cache`` for the lifetime of the process. The ``loom agent dev`` hot
loop needs those reads to reflect edits, so :func:`clear_config_caches` drops
every such cache. Tool *code* reloads for free: tools are imported via
``import_module_from_file``, which re-executes the file on each build rather than
caching it in ``sys.modules``. Helper modules those tools import from the shared
tools directory *are* cached there, so they are evicted here too.
"""

import logging

logger = logging.getLogger(__name__)


def clear_config_caches() -> None:
    """Drop every memoized config/file read so the next build re-reads from disk."""
    from loom.config.profiles import get_profiles
    from loom.core.loaders.agent import get_agent_config
    from loom.core.loaders.app import get_app_config
    from loom.core.loaders.workflow import get_workflow_config
    from loom.utils.loaders import (
        _load_absolute_config,
        _load_file_content,
        evict_workspace_modules,
    )

    for fn in (
        get_agent_config,
        get_app_config,
        get_workflow_config,
        get_profiles,
        _load_absolute_config,
        _load_file_content,
    ):
        fn.cache_clear()

    evict_workspace_modules()
    logger.debug("Config/file caches cleared for reload")
