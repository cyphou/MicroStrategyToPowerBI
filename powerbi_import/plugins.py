"""
Plugin system.

Provides extension points that allow users to register custom hooks
for the migration pipeline:

- **pre_generate**: Called before PBIP generation with (data, config) → modified data.
- **post_generate**: Called after generation with (stats, output_dir) → None.
- **custom_visual**: Called for unknown visual types with (viz_def) → optional visual JSON.
- **custom_expression**: Called for unmapped MSTR functions with (func_name, args) → optional DAX string.

Plugins are plain Python modules placed in a ``plugins/`` directory
and registered via ``register_plugin()`` or auto-discovered.
"""

import importlib
import logging
import os
import sys

logger = logging.getLogger(__name__)

# ── Hook registry ────────────────────────────────────────────────

_hooks = {
    "pre_generate": [],
    "post_generate": [],
    "custom_visual": [],
    "custom_expression": [],
}


def register_hook(hook_name, callback):
    """Register a callback for the given hook point."""
    if hook_name not in _hooks:
        logger.warning("Unknown hook: %s (available: %s)", hook_name, list(_hooks.keys()))
        return
    _hooks[hook_name].append(callback)
    logger.debug("Registered %s hook: %s", hook_name, callback.__name__)


def fire_hook(hook_name, *args, **kwargs):
    """Fire all callbacks for a hook. Returns the last non-None result."""
    result = None
    for cb in _hooks.get(hook_name, []):
        try:
            r = cb(*args, **kwargs)
            if r is not None:
                result = r
        except Exception as e:
            logger.error("Plugin hook %s failed in %s: %s", hook_name, cb.__name__, e)
    return result


# ── Plugin discovery ─────────────────────────────────────────────


def discover_plugins(plugin_dir="plugins"):
    """Auto-discover and load plugins from a directory.

    Each ``.py`` file in *plugin_dir* is imported.  The module should call
    ``register_hook()`` during import to register its callbacks.
    """
    if not os.path.isdir(plugin_dir):
        return 0

    count = 0
    sys.path.insert(0, plugin_dir)
    for fname in sorted(os.listdir(plugin_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        mod_name = fname[:-3]
        try:
            importlib.import_module(mod_name)
            count += 1
            logger.info("Loaded plugin: %s", mod_name)
        except Exception as e:
            logger.error("Failed to load plugin %s: %s", mod_name, e)
    return count


def clear_hooks():
    """Clear all registered hooks (useful for testing)."""
    for k in _hooks:
        _hooks[k].clear()
