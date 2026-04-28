"""
Command line interface for the SMV tool.
"""

from __future__ import annotations

import argparse
from getpass import getpass
import os
import sys
import traceback
from typing import List, Optional

from smv import __version__, providers, user_config
from smv.config import check_dependencies
from smv.core import SmartMover


def _print_provider_menu(default_provider: str) -> str:
    provider_list = providers.ordered_providers()
    print("Choose AI provider:")
    for idx, provider in enumerate(provider_list, start=1):
        suffix = " (default)" if provider.id == default_provider else ""
        print(f"  {idx}. {provider.display_name} [{provider.id}]{suffix}")

    while True:
        choice = input("Provider number (or press Enter for default): ").strip()
        if not choice:
            return default_provider
        try:
            selected_index = int(choice) - 1
            if 0 <= selected_index < len(provider_list):
                return provider_list[selected_index].id
        except ValueError:
            pass
        print("Invalid choice. Try again.")


def _print_model_menu(
    provider_id: str,
    base_url: Optional[str],
    default_model: str,
) -> str:
    provider = providers.get_provider(provider_id)
    model_options = providers.list_models(provider.id, base_url=base_url)
    if not model_options:
        model_options = [default_model]

    print(f"Choose model for {provider.display_name}:")
    for idx, model in enumerate(model_options, start=1):
        suffix = " (default)" if model == default_model else ""
        print(f"  {idx}. {model}{suffix}")
    print(f"  {len(model_options) + 1}. Enter custom model")

    while True:
        choice = input("Model number (or press Enter for default): ").strip()
        if not choice:
            return default_model
        try:
            selected_index = int(choice)
            if 1 <= selected_index <= len(model_options):
                return model_options[selected_index - 1]
            if selected_index == len(model_options) + 1:
                custom_model = input("Custom model name: ").strip()
                if custom_model:
                    return custom_model
        except ValueError:
            pass
        print("Invalid choice. Try again.")


def _setup_ai_profile(
    provider_id: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    storage: str = "keyring",
) -> int:
    config = user_config.load_user_config()
    default_provider = config.get("provider", "ollama")
    selected_provider_id = provider_id or _print_provider_menu(default_provider)
    selected_provider = providers.get_provider(selected_provider_id)

    config["provider"] = selected_provider.id
    config["base_url"] = (
        base_url
        if base_url is not None
        else config.get("base_url") or selected_provider.default_base_url
    )
    if selected_provider.default_base_url and base_url is None:
        prompt_default = config.get("base_url") or selected_provider.default_base_url
        entered_base_url = input(
            f"Base URL [{prompt_default}] (press Enter to keep): "
        ).strip()
        if entered_base_url:
            config["base_url"] = entered_base_url

    default_model = model_name or config.get("model") or selected_provider.default_model
    config["model"] = (
        model_name
        if model_name is not None
        else _print_model_menu(selected_provider.id, config.get("base_url"), default_model)
    )

    user_config.save_user_config(config)

    needs_key = selected_provider.api_key_required
    provided_key = api_key
    if provided_key is None:
        if needs_key:
            provided_key = getpass(
                f"Enter API key for {selected_provider.display_name}: "
            ).strip()
        else:
            choice = input(
                f"{selected_provider.display_name} API key is optional. Set one now? (y/N): "
            ).strip().lower()
            if choice == "y":
                provided_key = getpass(
                    f"Enter API key for {selected_provider.display_name}: "
                ).strip()

    if provided_key:
        used_storage = user_config.set_api_key(
            config,
            provided_key,
            storage=storage,
            allow_plaintext_fallback=True,
        )
        print(
            f"Saved AI profile: provider={config['provider']}, model={config['model']}, storage={used_storage}"
        )
    else:
        if needs_key:
            print(
                f"Warning: {selected_provider.display_name} requires an API key. Set one with `smv ai set-api-key`."
            )
        print(f"Saved AI profile: provider={config['provider']}, model={config['model']}")
    return 0


def _show_ai_profile() -> int:
    raw = user_config.load_user_config()
    effective = user_config.get_effective_ai_config()
    provider = providers.get_provider(effective.get("provider", "ollama"))

    print(f"Config file: {user_config.get_config_path()}")
    print(f"Provider: {provider.display_name} ({provider.id})")
    print(f"Model: {effective.get('model')}")
    print(f"Base URL: {effective.get('base_url') or 'N/A'}")
    print(f"API key storage: {raw.get('api_key_storage', 'keyring')}")
    print("API key: configured" if effective.get("api_key") else "API key: missing")
    return 0


def _set_provider(provider_id: str) -> int:
    config = user_config.load_user_config()
    provider = providers.get_provider(provider_id)
    config["provider"] = provider.id
    config["model"] = provider.default_model
    config["base_url"] = provider.default_base_url
    user_config.save_user_config(config)
    print(
        f"Provider updated to {provider.display_name}. Use `smv ai set-model` to change model."
    )
    return 0


def _set_model(model_name: str) -> int:
    config = user_config.load_user_config()
    config["model"] = model_name
    user_config.save_user_config(config)
    print(f"Model updated to '{model_name}'.")
    return 0


def _set_base_url(base_url: str) -> int:
    config = user_config.load_user_config()
    config["base_url"] = base_url
    user_config.save_user_config(config)
    print(f"Base URL updated to '{base_url}'.")
    return 0


def _set_api_key(api_key: Optional[str], storage: str) -> int:
    config = user_config.load_user_config()
    provider = providers.get_provider(config.get("provider", "ollama"))
    key_to_store = api_key or getpass(f"Enter API key for {provider.display_name}: ").strip()
    if not key_to_store:
        print("No API key entered.")
        return 1
    used_storage = user_config.set_api_key(
        config,
        key_to_store,
        storage=storage,
        allow_plaintext_fallback=True,
    )
    print(f"API key saved using {used_storage} storage.")
    return 0


def _list_models(provider_id: Optional[str], base_url: Optional[str]) -> int:
    config = user_config.load_user_config()
    target_provider_id = provider_id or config.get("provider", "ollama")
    provider = providers.get_provider(target_provider_id)
    resolved_base_url = base_url or config.get("base_url") or provider.default_base_url

    models = providers.list_models(provider.id, base_url=resolved_base_url)
    print(f"Models for {provider.display_name}:")
    for model_name in models:
        print(f"  - {model_name}")
    return 0


def _normalize_argv(argv: List[str]) -> List[str]:
    if not argv:
        return argv
    command_roots = {"sort", "ai", "setup-ai"}
    first = argv[0]
    if first in command_roots or first.startswith("-"):
        return argv
    return ["sort", *argv]


def _run_sort(file_path_arg: str) -> int:
    print(f"Smart Move v{__version__} starting for: {file_path_arg}")
    check_dependencies()

    if not os.path.exists(file_path_arg):
        print(f"Error: File '{file_path_arg}' does not exist.")
        return 1
    if not os.path.isfile(file_path_arg):
        print(f"Error: Path '{file_path_arg}' is not a file.")
        return 1

    try:
        mover = SmartMover(file_path_arg, ai_settings=user_config.get_effective_ai_config())
        mover.sort_file()
        return 0
    except Exception as e:
        print(f"Critical error in execution: {e}")
        traceback.print_exc()
        return 1
    finally:
        print("\n--- End of Script ---")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smart Move (smv) - AI-powered file organization tool",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"SMV v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    sort_parser = subparsers.add_parser("sort", help="Analyze and move one file")
    sort_parser.add_argument("file_path", help="Path to the file to organize")

    setup_parser = subparsers.add_parser(
        "setup-ai", help="Interactive AI provider/model/API key setup"
    )
    setup_parser.add_argument(
        "--provider", choices=providers.provider_ids(), help="Provider id"
    )
    setup_parser.add_argument("--model", help="Model name override")
    setup_parser.add_argument("--base-url", help="Base URL override")
    setup_parser.add_argument("--api-key", help="API key to save")
    setup_parser.add_argument(
        "--storage",
        choices=["keyring", "plaintext"],
        default="keyring",
        help="API key storage mode",
    )

    ai_parser = subparsers.add_parser("ai", help="Manage AI provider settings")
    ai_subparsers = ai_parser.add_subparsers(dest="ai_command", required=True)

    ai_subparsers.add_parser("show", help="Show current AI profile")

    ai_setup = ai_subparsers.add_parser("setup", help="Interactive AI setup")
    ai_setup.add_argument("--provider", choices=providers.provider_ids())
    ai_setup.add_argument("--model")
    ai_setup.add_argument("--base-url")
    ai_setup.add_argument("--api-key")
    ai_setup.add_argument(
        "--storage", choices=["keyring", "plaintext"], default="keyring"
    )

    ai_set_provider = ai_subparsers.add_parser(
        "set-provider", help="Set provider and reset to provider defaults"
    )
    ai_set_provider.add_argument("provider", choices=providers.provider_ids())

    ai_set_model = ai_subparsers.add_parser("set-model", help="Set active model")
    ai_set_model.add_argument("model")

    ai_set_base_url = ai_subparsers.add_parser("set-base-url", help="Set base URL")
    ai_set_base_url.add_argument("base_url")

    ai_set_api_key = ai_subparsers.add_parser("set-api-key", help="Set API key")
    ai_set_api_key.add_argument("--key", help="API key value")
    ai_set_api_key.add_argument(
        "--storage", choices=["keyring", "plaintext"], default="keyring"
    )

    ai_list_models = ai_subparsers.add_parser(
        "list-models", help="List suggested/discovered models"
    )
    ai_list_models.add_argument("--provider", choices=providers.provider_ids())
    ai_list_models.add_argument("--base-url")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    normalized_argv = _normalize_argv(argv if argv is not None else sys.argv[1:])
    args = parser.parse_args(normalized_argv)

    if args.command == "sort":
        return _run_sort(args.file_path)

    if args.command == "setup-ai":
        return _setup_ai_profile(
            provider_id=args.provider,
            model_name=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            storage=args.storage,
        )

    if args.command == "ai":
        if args.ai_command == "show":
            return _show_ai_profile()
        if args.ai_command == "setup":
            return _setup_ai_profile(
                provider_id=args.provider,
                model_name=args.model,
                base_url=args.base_url,
                api_key=args.api_key,
                storage=args.storage,
            )
        if args.ai_command == "set-provider":
            return _set_provider(args.provider)
        if args.ai_command == "set-model":
            return _set_model(args.model)
        if args.ai_command == "set-base-url":
            return _set_base_url(args.base_url)
        if args.ai_command == "set-api-key":
            return _set_api_key(args.key, args.storage)
        if args.ai_command == "list-models":
            return _list_models(args.provider, args.base_url)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
