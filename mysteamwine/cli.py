from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from . import APP_NAME, DEFAULT_BOTTLE_NAME
from .advisor import recommend_dependencies
from .bottle import app_support_root, bottle_paths, ensure_bottle_dirs
from .dxmt import install_dxmt
from .dxvk import install_dxvk
from .runtime import is_apple_silicon, resolve_executable, resolve_with_fallback, run_logged
from .scanner import scan_game_dir
from .steam import (
    find_app,
    guess_game_executable,
    install_steam,
    launch_app,
    list_installed_apps,
    run_game_executable,
    run_steam,
    steam_windows_path,
)
from .winetricks import run_winetricks


def _require_wine64(args: argparse.Namespace) -> Path:
    wine_arg = args.wine64 or args.wine
    if not wine_arg:
        raise SystemExit("--wine64 is required for this command")
    return resolve_with_fallback(wine_arg, "wine64", ("wine",))


def cmd_info(args: argparse.Namespace) -> None:
    bottle = bottle_paths(args.bottle)
    print(f"APP SUPPORT ROOT: {app_support_root()}")
    print(f"BOTTLE ROOT:      {bottle.root}")
    print(f"PREFIX:           {bottle.prefix}")
    print(f"LOGS:             {bottle.logs}")
    print(f"DOWNLOADS:        {bottle.downloads}")
    print(f"CACHE:            {bottle.cache}")
    print(f"Apple Silicon:    {is_apple_silicon()}")


def cmd_init(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = bottle_paths(args.bottle)
    ensure_bottle_dirs(bottle)
    print(f"Initializing bottle '{bottle.name}' at: {bottle.prefix}")
    code, tail = run_logged(
        cmd=[str(wine64), "wineboot", "-u"],
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / "01_wineboot.log",
    )
    if code != 0:
        raise SystemExit(f"wineboot failed (exit {code}). Tail:\n{tail}")
    print("Done.")


def cmd_install_steam(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = bottle_paths(args.bottle)
    print(f"Installing Steam into bottle '{bottle.name}'...")
    code, tail = install_steam(bottle=bottle, wine64_path=wine64)
    if code != 0:
        raise SystemExit(f"Steam installer failed (exit {code}). Tail:\n{tail}")
    print("Steam install finished (or installer exited).")


def cmd_run_steam(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = bottle_paths(args.bottle)
    print(f"Launching Steam in bottle '{bottle.name}'...")
    code, tail = run_steam(
        bottle=bottle,
        wine64_path=wine64,
        steam_path=args.steam_path,
        wait=not args.no_wait,
        graphics_backend=args.graphics_backend,
    )
    if code != 0:
        raise SystemExit(f"Steam launch failed (exit {code}). Tail:\n{tail}")
    if args.no_wait:
        print("Steam launched.")
    else:
        print("Steam exited.")


def cmd_run_winetricks(args: argparse.Namespace) -> None:
    bottle = bottle_paths(args.bottle)
    winetricks = resolve_executable(args.winetricks, "winetricks")
    verbs = [verb.strip() for verb in args.verbs.split(",") if verb.strip()]
    if not verbs:
        raise SystemExit("At least one winetricks verb is required")
    code, tail = run_winetricks(bottle=bottle, winetricks_path=winetricks, verbs=verbs, unattended=not args.interactive)
    if code != 0:
        raise SystemExit(f"winetricks failed (exit {code}). Tail:\n{tail}")


def cmd_install_dxvk(args: argparse.Namespace) -> None:
    bottle = bottle_paths(args.bottle)
    code, tail = install_dxvk(
        bottle=bottle,
        dxvk_source=Path(args.dxvk_source),
        dxvk_flavor=args.dxvk_flavor,
        use_symlinks=args.symlink,
        without_dxgi=args.without_dxgi,
    )
    if code != 0:
        raise SystemExit(f"DXVK install failed (exit {code}). Tail:\n{tail}")


def cmd_install_dxmt(args: argparse.Namespace) -> None:
    bottle = bottle_paths(args.bottle)
    code, tail = install_dxmt(
        bottle=bottle,
        dxmt_source=Path(args.dxmt_source),
    )
    if code != 0:
        raise SystemExit(f"DXMT install failed (exit {code}). Tail:\n{tail}")


def cmd_list_games(args: argparse.Namespace) -> None:
    bottle = bottle_paths(args.bottle)
    apps = list_installed_apps(bottle)
    if not apps:
        print("No Steam manifests found.")
        return
    for app in apps:
        print(f"{app.appid}\t{app.name}\t{app.install_dir}")


def cmd_launch_game(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = bottle_paths(args.bottle)
    app = find_app(bottle, args.appid)
    print(f"Launching {app.name} ({app.appid}) via Steam.")
    code, tail = launch_app(
        bottle=bottle,
        wine64_path=wine64,
        appid=args.appid,
        graphics_backend=args.graphics_backend,
    )
    if code != 0:
        raise SystemExit(f"App launch failed (exit {code}). Tail:\n{tail}")


def _resolve_debug_executable(args: argparse.Namespace) -> Path:
    if args.exe:
        return Path(args.exe)
    if args.appid:
        bottle = bottle_paths(args.bottle)
        app = find_app(bottle, args.appid)
        return guess_game_executable(app.install_dir)
    raise SystemExit("Provide either --appid or --exe")


def cmd_debug_game(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = bottle_paths(args.bottle)
    executable = _resolve_debug_executable(args)
    extra_args = list(args.game_args or [])
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    print(f"Launching {executable.name} directly with Wine debug logging...")
    code, tail = run_game_executable(
        bottle=bottle,
        wine64_path=wine64,
        executable=executable,
        extra_args=extra_args,
        wine_debug=args.wine_debug,
        wait=not args.no_wait,
        graphics_backend=args.graphics_backend,
    )
    if code != 0:
        raise SystemExit(f"Direct game launch failed (exit {code}). Tail:\n{tail}")
    print("Game process exited.")


def _resolve_scan_target(args: argparse.Namespace) -> Path:
    if args.path:
        return Path(args.path)
    if args.appid:
        bottle = bottle_paths(args.bottle)
        return find_app(bottle, args.appid).install_dir
    raise SystemExit("Provide either --path or --appid")


def cmd_scan_game(args: argparse.Namespace) -> None:
    scan = scan_game_dir(_resolve_scan_target(args))
    if not scan.signals:
        print(f"No known dependency markers found in {scan.root}")
        return
    for signal in scan.signals:
        print(f"{signal.key}\t{signal.detail}\t{signal.path}")


def cmd_advise_game(args: argparse.Namespace) -> None:
    scan = scan_game_dir(_resolve_scan_target(args))
    recommendations = recommend_dependencies(scan)
    if not recommendations:
        print(f"No rules matched for {scan.root}")
        return
    for rec in recommendations:
        print(f"{rec.verb}\t{rec.reason}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mysteamwine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            f"""\
            {APP_NAME}: Python-first Wine bottle manager for Steam on macOS.

            Typical flow:
              1) init
              2) install-steam
              3) run-steam
              4) list-games
              5) launch-game --appid <id>
            """
        ),
    )
    parser.add_argument("--bottle", default=DEFAULT_BOTTLE_NAME, help=f"Bottle name (default: {DEFAULT_BOTTLE_NAME})")
    parser.add_argument(
        "--wine64",
        help="Path to the Wine launcher (example: /opt/homebrew/bin/wine or /opt/homebrew/bin/wine64)",
    )
    parser.add_argument("--wine", dest="wine", help="Alias for --wine64 for compatibility with older usage")
    parser.add_argument(
        "--graphics-backend",
        choices=("dxvk", "dxmt", "none"),
        default="dxvk",
        help="Graphics backend override to apply at launch time (default: dxvk)",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Show paths used for this bottle").set_defaults(func=cmd_info)
    sub.add_parser("init", help="Create or initialize the Wine prefix").set_defaults(func=cmd_init)
    sub.add_parser("install-steam", help="Download and run SteamSetup.exe").set_defaults(func=cmd_install_steam)

    run_cmd = sub.add_parser("run-steam", help="Launch Steam.exe inside the bottle")
    run_cmd.add_argument("--steam-path", default=steam_windows_path(), help="Windows path to Steam.exe")
    run_cmd.add_argument("--no-wait", action="store_true", help="Return immediately after launching Steam")
    run_cmd.set_defaults(func=cmd_run_steam)

    tricks_cmd = sub.add_parser("winetricks", help="Run winetricks verbs against the bottle")
    tricks_cmd.add_argument("--winetricks", default="winetricks", help="Path to the winetricks executable")
    tricks_cmd.add_argument("--verbs", required=True, help="Comma-separated verbs, for example: vcrun2019,d3dx9")
    tricks_cmd.add_argument("--interactive", action="store_true", help="Run winetricks without -q")
    tricks_cmd.set_defaults(func=cmd_run_winetricks)

    dxvk_cmd = sub.add_parser("install-dxvk", help="Install DXVK into the bottle from a local folder or tar.gz")
    dxvk_cmd.add_argument("--dxvk-source", required=True, help="Path to a DXVK directory or tar.gz archive")
    dxvk_cmd.add_argument(
        "--dxvk-flavor",
        choices=("upstream", "macos"),
        default="upstream",
        help="DXVK layout to install (default: upstream)",
    )
    dxvk_cmd.add_argument("--symlink", action="store_true", help="Use symlinks instead of copying DLLs")
    dxvk_cmd.add_argument("--without-dxgi", action="store_true", help="Skip dxgi.dll override")
    dxvk_cmd.set_defaults(func=cmd_install_dxvk)

    dxmt_cmd = sub.add_parser("install-dxmt", help="Install DXMT into the bottle from a local folder or tar.gz")
    dxmt_cmd.add_argument("--dxmt-source", required=True, help="Path to a DXMT directory or tar.gz archive")
    dxmt_cmd.set_defaults(func=cmd_install_dxmt)

    sub.add_parser("list-games", help="List installed Steam games discovered from manifests").set_defaults(func=cmd_list_games)

    launch_cmd = sub.add_parser("launch-game", help="Launch a Steam game by AppID")
    launch_cmd.add_argument("--appid", required=True, help="Steam AppID")
    launch_cmd.set_defaults(func=cmd_launch_game)

    debug_cmd = sub.add_parser("debug-game", help="Launch a game executable directly with Wine debug logging")
    debug_cmd.add_argument("--appid", help="Steam AppID to resolve to an installed game executable")
    debug_cmd.add_argument("--exe", help="Explicit path to a Windows game executable inside the bottle")
    debug_cmd.add_argument("--wine-debug", default="+timestamp,+seh,+loaddll", help="WINEDEBUG value for the direct launch")
    debug_cmd.add_argument("--no-wait", action="store_true", help="Return immediately after launching the executable")
    debug_cmd.add_argument("game_args", nargs=argparse.REMAINDER, help="Arguments passed through to the game after --")
    debug_cmd.set_defaults(func=cmd_debug_game)

    for name, handler, help_text in (
        ("scan-game", cmd_scan_game, "Scan a game folder for dependency markers"),
        ("advise-game", cmd_advise_game, "Recommend winetricks verbs for a game folder"),
    ):
        scan_cmd = sub.add_parser(name, help=help_text)
        scan_cmd.add_argument("--appid", help="Scan a known Steam game by AppID")
        scan_cmd.add_argument("--path", help="Scan an explicit game directory")
        scan_cmd.set_defaults(func=handler)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if is_apple_silicon():
        print("[Note] You’re on Apple Silicon. Many Wine/Steam setups run under Rosetta 2.")

    args.func(args)
