#!/usr/bin/env python3
"""Prompt Improver CLI. Every command prints JSON; `improve` prints NDJSON events.

  promptctl.py improve --target claude/opus-5.5 [--context auto|CATEGORY]
                       [--text TEXT | stdin] [--english TEXT --source LANG]
                       [--backend PROFILE] [--ui-lang es] [--no-save]
  promptctl.py models [--refresh]
  promptctl.py engines [--refresh]          detected local AI CLIs + usable API profiles
  promptctl.py history list [--q TEXT] [--category C] [--family F] [--fav] [--limit N]
  promptctl.py history get|delete|fav ID
  promptctl.py history stats
  promptctl.py history export [--format md|json]
  promptctl.py config show | path | init | set KEY VALUE
  promptctl.py guide FAMILY/VERSION
"""
import argparse
import json
import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from promptkit import backends, catalog, config, engines, rewrite, store, translate  # noqa: E402
from promptkit import paths  # noqa: E402

MAX_INPUT = 20000


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def fail(message, code=1):
    emit({"ok": False, "error": str(message)[:300]})
    sys.exit(code)


# ------------------------------------------------------------------ improve

def cmd_improve(args):
    text = args.text if args.text is not None else sys.stdin.read()
    text = (text or "").strip()
    if not text:
        fail("empty text")
    if len(text) > MAX_INPUT:
        fail(f"text too long ({len(text)} > {MAX_INPUT} characters)")

    cfg = config.load()
    config.ensure_file()
    try:
        cat = catalog.load()
        target = args.target or cfg.get("last_target") or cat.get("default")
        family, version = catalog.resolve(target, cat)
    except (catalog.CatalogError, OSError, ValueError) as e:
        fail(e)

    forced = args.context if args.context and args.context != "auto" else None
    if forced and forced not in catalog.CATEGORIES:
        fail(f"unknown context {forced!r}")

    # 1. language: detect and translate to English (skipped when the UI already has it)
    if args.english is not None and args.source:
        english, source = args.english.strip() or text, args.source[:16]
    else:
        emit({"stage": "translating"})
        try:
            english, source = translate.to_english(text)
        except translate.TranslateError as e:
            # Translation is a convenience; the rewriter handles any language.
            english, source = "", "?"
            emit({"stage": "translate_failed", "error": str(e)[:200]})
    emit({"stage": "translated", "source": source, "english": english if source != "en" else ""})

    # 2. rewrite
    try:
        backend_choice = backends.resolve(cfg, args.backend)
    except backends.BackendError as e:
        fail(e)
    emit({"stage": "rewriting", "target": version["label"], "backend": backend_choice})
    ui_lang = (args.ui_lang or cfg.get("ui_lang") or "es").split("-")[0]
    try:
        system = rewrite.build_system(family, version, ui_lang, forced)
    except (OSError, catalog.CatalogError) as e:
        fail(f"guide: {e}")
    user = rewrite.build_user(text, source, english, version)

    result, backend_name, last_error = None, "", None
    for _attempt in range(2):
        try:
            backend_name, raw = backends.run(cfg, system, user, rewrite.SCHEMA, backend_choice)
            result = rewrite.validate(raw, forced)
            break
        except (backends.BackendError, rewrite.RewriteError) as e:
            last_error = e
            # Only malformed output is worth one retry; config/network errors are not.
            if not ("JSON" in str(e) or isinstance(e, rewrite.RewriteError)):
                break
    if result is None:
        fail(last_error or "rewrite failed")

    # Some models answer in the user's language despite the rule; check and retry once.
    if source not in ("en", "?"):
        lang = translate.detect(result["improved_prompt"])
        if lang and lang != "en":
            emit({"stage": "retrying", "reason": f"prompt came back in {lang}"})
            retry_user = user + "\n\n" + rewrite.LANG_CORRECTION.format(lang=lang)
            try:
                backend_name, raw = backends.run(cfg, system, retry_user, rewrite.SCHEMA, backend_choice)
                result = rewrite.validate(raw, forced)
            except (backends.BackendError, rewrite.RewriteError):
                pass  # keep the first result

    _, reviewed = catalog.read_guide(family)
    guide_ref = f"{family['guide']}@{reviewed}"
    target_id = f"{family['id']}/{version['id']}"
    entry_id = None
    if not args.no_save:
        try:
            db = store.Store()
            entry_id = db.add({
                "source_lang": source,
                "original": text,
                "english": english if source != "en" else "",
                "improved": result["improved_prompt"],
                "family": family["id"],
                "version": version["id"],
                "target_label": version["label"],
                "category": result["category"],
                "subtype": result["subtype"],
                "title": result["title"],
                "tags": result["tags"],
                "backend": backend_name,
                "guide": guide_ref,
                "changes": result["changes"],
            })
            db.close()
        except Exception as e:  # history is best effort; never lose the result
            emit({"stage": "save_failed", "error": str(e)[:200]})
    try:
        config.remember_target(target_id)
    except OSError:
        pass

    emit({
        "ok": True,
        "id": entry_id,
        "target": target_id,
        "target_label": version["label"],
        "source": source,
        "context": {k: result[k] for k in ("category", "subtype", "title", "tags")},
        "improved": result["improved_prompt"],
        "changes": result["changes"],
        "guide": guide_ref,
        "backend": backend_name,
    })


# ------------------------------------------------------------------- others

def cmd_models(args):
    cfg = config.load()
    data = catalog.public()
    data["ok"] = True
    data["last_target"] = cfg.get("last_target") or data["default"]
    data["backend"] = cfg.get("backend") or "auto"
    data["ui_lang"] = cfg.get("ui_lang", "es")
    data["engines"] = backends.available(cfg, getattr(args, "refresh", False))
    try:
        data["resolved_backend"] = backends.resolve(cfg)
    except backends.BackendError:
        data["resolved_backend"] = ""
    emit(data)


def cmd_engines(args):
    cfg = config.load()
    detected = engines.detect(args.refresh)
    emit({
        "ok": True,
        "backend": cfg.get("backend") or "auto",
        "available": backends.available(cfg),
        "detected": {k: {"label": engines.ENGINES[k]["label"], **v} for k, v in detected.items()},
    })


def cmd_history(args):
    db = store.Store()
    try:
        if args.action == "list":
            emit({"ok": True, "items": db.list(args.q or "", args.category or "", args.family or "", args.fav, args.limit)})
        elif args.action == "stats":
            emit({"ok": True, **db.stats()})
        elif args.action == "export":
            items = [db.get(i["id"]) for i in db.list(limit=1000)]
            if args.format == "md":
                for it in items:
                    print(f"## {it['title'] or it['id']}\n")
                    print(f"- {it['created']} · {it['target_label']} · {it['category']}/{it['subtype']} · {', '.join(it['tags'])}\n")
                    print("```text\n" + it["improved"] + "\n```\n")
            else:
                print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            if args.id is None:
                fail("missing id")
            if args.action == "get":
                item = db.get(args.id)
                emit({"ok": True, "item": item} if item else {"ok": False, "error": "not found"})
            elif args.action == "delete":
                emit({"ok": db.delete(args.id), "id": args.id})
            elif args.action == "fav":
                fav = db.set_favorite(args.id)
                emit({"ok": fav is not None, "id": args.id, "favorite": bool(fav)})
    finally:
        db.close()


def cmd_config(args):
    if args.action == "path":
        emit({"ok": True, "config": str(paths.config_path()), "history": str(paths.history_path())})
    elif args.action == "init":
        config.ensure_file()
        emit({"ok": True, "config": str(paths.config_path())})
    elif args.action == "set":
        if not args.key or args.value is None:
            fail("usage: config set KEY VALUE")
        try:
            config.set_value(args.key, args.value)
        except ValueError as e:
            fail(e)
        emit({"ok": True})
    else:
        emit({"ok": True, "config": config.load()})


def cmd_guide(args):
    try:
        family, version = catalog.resolve(args.target)
        body, reviewed = catalog.read_guide(family)
    except (catalog.CatalogError, OSError) as e:
        fail(e)
    print(f"# {version['label']} — guide {family['guide']} (reviewed {reviewed})\n\n{body}")


def parser():
    p = argparse.ArgumentParser(prog="promptctl", description="Improve prompts for a target LLM.")
    sub = p.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("improve")
    imp.add_argument("--target")
    imp.add_argument("--context", default="auto")
    imp.add_argument("--text")
    imp.add_argument("--english")
    imp.add_argument("--source")
    imp.add_argument("--backend")
    imp.add_argument("--ui-lang")
    imp.add_argument("--no-save", action="store_true")
    imp.set_defaults(fn=cmd_improve)

    mod = sub.add_parser("models")
    mod.add_argument("--refresh", action="store_true", help="re-detect installed CLIs")
    mod.set_defaults(fn=cmd_models)

    eng = sub.add_parser("engines")
    eng.add_argument("--refresh", action="store_true")
    eng.set_defaults(fn=cmd_engines)

    hist = sub.add_parser("history")
    hist.add_argument("action", choices=["list", "get", "delete", "fav", "stats", "export"])
    hist.add_argument("id", nargs="?", type=int)
    hist.add_argument("--q")
    hist.add_argument("--category")
    hist.add_argument("--family")
    hist.add_argument("--fav", action="store_true")
    hist.add_argument("--limit", type=int, default=200)
    hist.add_argument("--format", choices=["md", "json"], default="json")
    hist.set_defaults(fn=cmd_history)

    conf = sub.add_parser("config")
    conf.add_argument("action", choices=["show", "path", "init", "set"], nargs="?", default="show")
    conf.add_argument("key", nargs="?")
    conf.add_argument("value", nargs="?")
    conf.set_defaults(fn=cmd_config)

    guide = sub.add_parser("guide")
    guide.add_argument("target")
    guide.set_defaults(fn=cmd_guide)
    return p


def _on_term(_signum, _frame):
    backends.terminate_child()
    sys.exit(143)


def main(argv=None):
    signal.signal(signal.SIGTERM, _on_term)
    args = parser().parse_args(argv)
    try:
        args.fn(args)
    except BrokenPipeError:
        pass
    except Exception as e:  # never leave the UI without a final JSON line
        fail(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
