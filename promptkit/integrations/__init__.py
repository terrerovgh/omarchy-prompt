"""One module per AI CLI. Each exposes ENGINE (see promptkit.engines).

claude and codex are the built-in engines. The rest are optional
integrations: they are imported and probed only after
`promptctl.py integration install <name>`.
"""
