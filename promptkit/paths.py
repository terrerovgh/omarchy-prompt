"""Filesystem locations (XDG) and the plugin's own directory."""
import os
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
GUIDES_DIR = PLUGIN_DIR / "guides"
CATALOG_PATH = PLUGIN_DIR / "models.json"


def _xdg(var, fallback):
    value = os.environ.get(var)
    return Path(value) if value and os.path.isabs(value) else Path.home() / fallback


def config_dir():
    override = os.environ.get("OMARCHY_PROMPT_CONFIG_DIR")
    if override and os.path.isabs(override):
        return Path(override)
    return _xdg("XDG_CONFIG_HOME", ".config") / "omarchy-prompt"


def data_dir():
    return _xdg("XDG_DATA_HOME", ".local/share") / "omarchy-prompt"


def config_path():
    return config_dir() / "config.json"


def history_path():
    override = os.environ.get("OMARCHY_PROMPT_DB")
    return Path(override) if override else data_dir() / "history.sqlite3"
