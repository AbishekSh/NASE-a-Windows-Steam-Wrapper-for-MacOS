from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import textwrap
import time
import uuid
from pathlib import Path

from . import APP_NAME, DEFAULT_BOTTLE_NAME
from .advisor import recommend_dependencies
from .bottle import app_support_root, bottle_paths, ensure_bottle_dirs, external_prefix_paths, wipe_all_bottles
from .catalog import install_runtime, list_installed_runtimes, list_runtime_catalog
from .d3dmetal import d3dmetal_launch_environment, install_d3dmetal, verify_d3dmetal_profile
from .dependencies import dependency_install_command, dependency_status
from .doctor import apply_doctor_fixes, run_doctor, set_prefix_windows_version
from .dxmt import install_dxmt
from .dxvk import install_dxvk
from .dxvk_macos import (
    discover_moltenvk_source,
    install_dxvk_macos_native_runtime,
    probe_dxvk_macos_graphics,
    verify_dxvk_macos_profile,
)
from .gptk import discover_gptk_installations, import_managed_gptk, prepare_sikarugir_native_dependencies
from .library_activity import acquire_steam_activity, assert_direct_launch_safe, release_steam_activity
from .profiles import PROFILES, bind_profile, list_profiles, mark_profile_ready
from .runtime import detect_wine_runtime, is_apple_silicon, resolve_executable, resolve_with_fallback, run_logged
from .scanner import scan_game_dir
from .sessions import create_session, mark_steam_opened_by_user, reconcile_sessions, steam_is_running, stop_session, update_session
from .steam import (
    guess_game_executable,
    install_steam,
    kill_wine_processes,
    launch_app,
    probe_steam_stability,
    run_game_executable,
    run_steam,
    steam_windows_path,
)
from .steam_libraries import attach_registered_libraries, installed_games, refresh_registry, resolve_registered_app
from .winetricks import run_winetricks


def _json_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def _stream_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "jsonl", False))


def _emit_json(
    *,
    action: str,
    ok: bool,
    message: str,
    data: dict | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    status: str | None = None,
    job_id: str | None = None,
) -> None:
    print(
        json.dumps(
            {
                "ok": ok,
                "action": action,
                "status": status or ("completed" if ok else "failed"),
                "job_id": job_id or uuid.uuid4().hex,
                "message": message,
                "data": data or {},
                "warnings": warnings or [],
                "errors": errors or [],
            }
        )
    )


def _emit_stream_event(
    *,
    event: str,
    action: str,
    job_id: str,
    status: str,
    message: str,
    data: dict | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    ok: bool | None = None,
) -> None:
    print(
        json.dumps(
            {
                "event": event,
                "job_id": job_id,
                "action": action,
                "status": status,
                "message": message,
                "ok": ok,
                "data": data or {},
                "warnings": warnings or [],
                "errors": errors or [],
            }
        ),
        flush=True,
    )


def _stream_start(*, action: str, message: str) -> str:
    job_id = uuid.uuid4().hex
    _emit_stream_event(
        event="job",
        action=action,
        job_id=job_id,
        status="started",
        message=message,
    )
    return job_id


def _stream_step(*, action: str, job_id: str, name: str, status: str, message: str) -> None:
    _emit_stream_event(
        event="step",
        action=action,
        job_id=job_id,
        status=status,
        message=message,
        data={"step": {"name": name, "status": status}},
    )


def _stream_progress(
    *,
    action: str,
    job_id: str,
    name: str,
    status: str,
    message: str,
    completed_steps: int,
    total_steps: int,
) -> None:
    progress = completed_steps / total_steps if total_steps else None
    _emit_stream_event(
        event="step",
        action=action,
        job_id=job_id,
        status=status,
        message=message,
        data={
            "step": {"name": name, "status": status},
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "progress": progress,
        },
    )


def _stream_result(
    *,
    action: str,
    job_id: str,
    ok: bool,
    status: str,
    message: str,
    data: dict | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> None:
    _emit_stream_event(
        event="result",
        action=action,
        job_id=job_id,
        status=status,
        message=message,
        ok=ok,
        data=data,
        warnings=warnings,
        errors=errors,
    )


def _json_error(args: argparse.Namespace, *, action: str, message: str, code: int = 1, data: dict | None = None) -> None:
    if _stream_enabled(args):
        _stream_result(
            action=action,
            job_id=uuid.uuid4().hex,
            ok=False,
            status="failed",
            message=message,
            data=data,
            errors=[message],
        )
        raise SystemExit(code)
    if _json_enabled(args):
        _emit_json(action=action, ok=False, message=message, data=data, errors=[message], status="failed")
        raise SystemExit(code)
    raise SystemExit(message if code == 1 else code)


def _require_wine64(args: argparse.Namespace) -> Path:
    wine_arg = args.wine64 or args.wine
    if not wine_arg:
        raise SystemExit("--wine64 is required for this command")
    return resolve_with_fallback(wine_arg, "wine64", ("wine",))


def _resolve_bottle(args: argparse.Namespace):
    if getattr(args, "prefix", None):
        return external_prefix_paths(Path(args.prefix))
    return bottle_paths(args.bottle)


def _is_external_prefix(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "prefix", None))


def _target_label(args: argparse.Namespace, bottle) -> str:
    if _is_external_prefix(args):
        return f"external prefix '{bottle.prefix}'"
    return f"managed bottle '{bottle.name}'"


def _resolved_graphics_backend(args: argparse.Namespace, *, for_steam: bool) -> str:
    if args.graphics_backend == "auto":
        return "none" if for_steam else "dxmt"
    return args.graphics_backend


def _bind_launch_profile(args: argparse.Namespace, *, action: str, bottle, wine_path: Path, graphics_backend: str) -> str:
    defaults = {
        "dxmt": "dxmt-wine-stable-11-v1",
        "d3dmetal": "d3dmetal-gptk-v1",
        "dxvk": "dxvk-macos-pinned-v1",
        "none": "plain-wine-v1",
    }
    profile_id = getattr(args, "compatibility_profile", None) or defaults[graphics_backend]
    source_value = {
        "dxmt": getattr(args, "dxmt_source", None),
        "d3dmetal": getattr(args, "d3dmetal_source", None),
        "dxvk": getattr(args, "dxvk_source", None),
        "none": None,
    }[graphics_backend]
    try:
        if graphics_backend == "d3dmetal":
            free_bytes = shutil.disk_usage(bottle.root.parent).free
            if free_bytes < 2 * 1024**3:
                free_mib = free_bytes // (1024 * 1024)
                raise RuntimeError(
                    f"D3DMetal setup needs at least 2 GiB of free disk space for Wine, Steam updates, and temporary files; "
                    f"only {free_mib} MiB is available. Free some space, then retry Set Up."
                )
        bind_profile(
            bottle=bottle,
            profile_id=profile_id,
            graphics_backend=graphics_backend,
            wine_path=wine_path,
            graphics_source=Path(source_value) if source_value else None,
        )
    except RuntimeError as exc:
        _json_error(args, action=action, message=f"Compatibility profile is not ready: {exc}")
    return profile_id


def cmd_info(args: argparse.Namespace) -> None:
    bottle = _resolve_bottle(args)
    print(f"TARGET:           {_target_label(args, bottle)}")
    print(f"APP SUPPORT ROOT: {app_support_root()}")
    print(f"BOTTLE ROOT:      {bottle.root}")
    print(f"PREFIX:           {bottle.prefix}")
    print(f"LOGS:             {bottle.logs}")
    print(f"DOWNLOADS:        {bottle.downloads}")
    print(f"CACHE:            {bottle.cache}")
    print(f"Apple Silicon:    {is_apple_silicon()}")


def cmd_list_compatibility_profiles(args: argparse.Namespace) -> None:
    profiles = list_profiles()
    if _stream_enabled(args):
        job_id = _stream_start(action="list-compatibility-profiles", message="Loading compatibility profiles...")
        _stream_result(
            action="list-compatibility-profiles",
            job_id=job_id,
            ok=True,
            status="completed",
            message=f"Found {len(profiles)} compatibility profiles.",
            data={"profiles": profiles},
        )
        return
    if _json_enabled(args):
        _emit_json(
            action="list-compatibility-profiles",
            ok=True,
            message="Compatibility profiles listed.",
            data={"profiles": profiles},
        )
        return
    for profile in profiles:
        state = "ready" if profile["ready"] else "unavailable"
        print(f"{profile['id']}\t{state}\t{profile['name']}")


def cmd_discover_d3dmetal(args: argparse.Namespace) -> None:
    action = "discover-d3dmetal"
    installations = discover_gptk_installations(
        configured_wine=Path(args.gptk_wine) if args.gptk_wine else None,
        configured_source=Path(args.d3dmetal_source) if args.d3dmetal_source else None,
    )
    selected = installations[0] if installations else None
    message = "Found a matched Game Porting Toolkit installation." if selected else "No complete Game Porting Toolkit installation was found."
    data = {
        "installations": installations,
        "gptk_wine_path": selected["wine_path"] if selected else None,
        "d3dmetal_source": selected["d3dmetal_source"] if selected else None,
    }
    if _json_enabled(args) or _stream_enabled(args):
        _emit_json(action=action, ok=bool(selected), message=message, data=data, warnings=[] if selected else ["Install Apple's Game Porting Toolkit, then choose its folder in Advanced Settings."])
        if not selected:
            raise SystemExit(1)
        return
    print(message)
    if selected:
        print(f"Wine: {selected['wine_path']}")
        print(f"D3DMetal: {selected['d3dmetal_source']}")


def cmd_import_gptk(args: argparse.Namespace) -> None:
    action = "import-gptk"
    try:
        installed = import_managed_gptk(
            wine_path=Path(args.gptk_wine),
            d3dmetal_source=Path(args.d3dmetal_source),
            confirm_license=args.confirm_license,
        )
    except Exception as exc:
        _json_error(args, action=action, message=str(exc), code=1)
        return
    data = {
        "gptk_wine_path": installed["wine_path"],
        "d3dmetal_source": installed["installation_root"],
        "installation": installed,
    }
    message = f"Installed a managed Game Porting Toolkit runtime at {installed['installation_root']}."
    if _json_enabled(args) or _stream_enabled(args):
        _emit_json(action=action, ok=True, message=message, data=data)
    else:
        print(message)


def cmd_dependency_status(args: argparse.Namespace) -> None:
    action = "dependency-status"
    wine = Path(args.wine or args.wine64 or "/opt/homebrew/bin/wine")
    result = dependency_status(
        wine_path=wine,
        winetricks_path=args.winetricks,
        gptk_wine_path=Path(args.gptk_wine) if args.gptk_wine else None,
        d3dmetal_source=Path(args.d3dmetal_source) if args.d3dmetal_source else None,
    )
    missing = result["missing_required"]
    message = "Dependencies are ready." if not missing else f"Missing required dependencies: {', '.join(missing)}."
    if _stream_enabled(args):
        job_id = _stream_start(action=action, message="Checking host dependencies...")
        _stream_result(action=action, job_id=job_id, ok=not missing, status="completed" if not missing else "failed", message=message, data=result)
        return
    if _json_enabled(args):
        _emit_json(action=action, ok=not missing, message=message, data=result, status="completed" if not missing else "failed")
        return
    for check in result["checks"]:
        print(f"[{check['status'].upper():4}] {check['name']}: {check['detail']}")


def cmd_install_host_dependency(args: argparse.Namespace) -> None:
    action = "install-host-dependency"
    try:
        command = dependency_install_command(
            args.dependency,
            confirm_rosetta_license=args.confirm_rosetta_license,
        )
    except RuntimeError as exc:
        _json_error(args, action=action, message=str(exc))
    job_id = _stream_start(action=action, message=f"Installing {args.dependency}...") if _stream_enabled(args) else None
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        message = f"Could not install {args.dependency}: {exc}"
        if _stream_enabled(args):
            _stream_result(action=action, job_id=job_id or uuid.uuid4().hex, ok=False, status="failed", message=message, errors=[message])
            raise SystemExit(1)
        _json_error(args, action=action, message=message, code=1)
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    tail = "\n".join(output.splitlines()[-80:])
    if result.returncode != 0:
        message = f"{args.dependency} installation failed (exit {result.returncode})."
        if _stream_enabled(args):
            _stream_result(action=action, job_id=job_id or uuid.uuid4().hex, ok=False, status="failed", message=message, data={"dependency": args.dependency, "tail": tail}, errors=[message])
            raise SystemExit(result.returncode)
        _json_error(args, action=action, message=f"{message}\n{tail}", code=result.returncode)
    message = f"Installed {args.dependency}."
    data = {"dependency": args.dependency, "command": command, "tail": tail}
    if _stream_enabled(args):
        _stream_result(action=action, job_id=job_id or uuid.uuid4().hex, ok=True, status="completed", message=message, data=data)
    elif _json_enabled(args):
        _emit_json(action=action, ok=True, message=message, data=data)
    else:
        print(message)


def cmd_setup_compatibility_profile(args: argparse.Namespace) -> None:
    action = "setup-compatibility-profile"
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    if _is_external_prefix(args):
        _json_error(args, action=action, message="Compatibility profiles require a dedicated managed bottle.")
    profile_id = args.profile
    backend_by_profile = {
        "dxmt-wine-stable-11-v1": "dxmt",
        "d3dmetal-gptk-v1": "d3dmetal",
        "dxvk-macos-pinned-v1": "dxvk",
        "plain-wine-v1": "none",
    }
    if profile_id not in backend_by_profile:
        _json_error(args, action=action, message=f"Unknown compatibility profile: {profile_id}")
    graphics_backend = backend_by_profile[profile_id]
    source_value = {
        "dxmt": args.dxmt_source,
        "d3dmetal": args.d3dmetal_source,
        "dxvk": args.dxvk_source,
        "none": None,
    }[graphics_backend]
    graphics_source = Path(source_value) if source_value else None
    moltenvk_source = Path(args.moltenvk_source) if args.moltenvk_source else None
    if graphics_backend == "dxvk" and moltenvk_source is None:
        moltenvk_source = discover_moltenvk_source()
    graphics_environment = (
        d3dmetal_launch_environment(graphics_source)
        if graphics_backend == "d3dmetal" and graphics_source is not None
        else {}
    )
    job_id = _stream_start(action=action, message=f"Preparing {profile_id} in {bottle.name}...") if _stream_enabled(args) else None
    steps: list[dict[str, str]] = []

    def run_step(name: str, message: str, operation) -> None:
        if _stream_enabled(args):
            _stream_step(action=action, job_id=job_id or uuid.uuid4().hex, name=name, status="started", message=message)
        code, tail = operation()
        if code != 0:
            raise RuntimeError(f"{message} failed (exit {code}). Tail:\n{tail}")
        steps.append({"name": name, "status": "ok"})
        if _stream_enabled(args):
            _stream_progress(
                action=action,
                job_id=job_id or uuid.uuid4().hex,
                name=name,
                status="ok",
                message=message.replace("...", "") + " complete.",
                completed_steps=len(steps),
                total_steps=5,
            )

    try:
        if graphics_backend == "dxvk":
            free_bytes = shutil.disk_usage(bottle.root.parent).free
            minimum_bytes = 4 * 1024**3
            if free_bytes < minimum_bytes:
                raise RuntimeError(
                    f"DXVK-macOS setup needs at least 4 GiB free for its fresh bottle and Steam update; "
                    f"only {free_bytes // (1024**2)} MiB is available."
                )
            steps.append({"name": "disk-space", "status": "ok"})
        bind_profile(
            bottle=bottle,
            profile_id=profile_id,
            graphics_backend=graphics_backend,
            wine_path=wine64,
            graphics_source=graphics_source,
            moltenvk_source=moltenvk_source,
            require_ready=False,
        )
        if graphics_backend == "dxvk":
            manifest_path = bottle.root / "compatibility-profile.json"
            bound_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            install_dxvk_macos_native_runtime(bottle, bound_manifest["dxvk_macos_stack"])
            steps.append({"name": "install-native-runtime", "status": "ok"})
        if graphics_backend == "d3dmetal" and graphics_source is not None:
            native_dependency = prepare_sikarugir_native_dependencies(wine64, graphics_source)
            steps.append({"name": "verify-native-dependencies", "status": "ok"})
            if _stream_enabled(args):
                _stream_progress(
                    action=action,
                    job_id=job_id or uuid.uuid4().hex,
                    name="verify-native-dependencies",
                    status="ok",
                    message=(
                        f"Verified {native_dependency['verified_library_count']} native libraries, including "
                        f"{native_dependency['dependency']} ({native_dependency['sha256'][:12]}...)."
                    ),
                    completed_steps=len(steps),
                    total_steps=6,
                )
        ensure_bottle_dirs(bottle)
        steam_exe = bottle.drive_c / "Program Files (x86)" / "Steam" / "Steam.exe"
        initialized_prefix = (bottle.prefix / "system.reg").is_file() and steam_exe.is_file()
        if initialized_prefix:
            # A Wine update pass can launch Steam through its registry startup entry
            # and then wait forever for the client to exit. Profile setup retries only
            # need to resume graphics/library verification once Steam is installed.
            steps.extend(
                [
                    {"name": "wineboot", "status": "ok"},
                    {"name": "set-win10", "status": "ok"},
                ]
            )
        else:
            run_step(
                "wineboot",
                "Initializing the dedicated bottle...",
                lambda: run_logged(
                    cmd=[str(wine64), "wineboot", "-u"],
                    env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all", **graphics_environment},
                    log_file=bottle.logs / "01_profile_wineboot.log",
                    timeout=120,
                ),
            )
            run_step(
                "set-win10",
                "Setting Windows 10 compatibility...",
                lambda: set_prefix_windows_version(bottle, wine64, "win10", extra_env=graphics_environment),
            )
        if steam_exe.exists():
            steps.append({"name": "install-steam", "status": "ok"})
        else:
            winetricks = resolve_executable(args.winetricks, "winetricks")
            run_step(
                "install-steam",
                "Installing Steam...",
                lambda: run_winetricks(
                    bottle=bottle,
                    winetricks_path=winetricks,
                    verbs=["steam"],
                    log_name="02_profile_steam.log",
                    unattended=not args.interactive,
                    extra_env=graphics_environment,
                    wine_path=wine64,
                ),
            )
        if graphics_backend == "dxmt":
            run_step(
                "install-graphics",
                "Installing DXMT 0.71...",
                lambda: install_dxmt(bottle=bottle, dxmt_source=graphics_source, wine64_path=wine64),
            )
        elif graphics_backend == "d3dmetal":
            run_step(
                "install-graphics",
                "Installing the matching D3DMetal payload...",
                lambda: install_d3dmetal(bottle=bottle, d3dmetal_source=graphics_source, wine64_path=wine64),
            )
            verification = verify_d3dmetal_profile(bottle, graphics_source)
            failed = [check for check in verification if check["status"] != "ok"]
            if failed:
                raise RuntimeError("D3DMetal verification failed: " + "; ".join(check["detail"] for check in failed))
            steps.append({"name": "verify-graphics", "status": "ok"})
        elif graphics_backend == "dxvk":
            run_step(
                "install-graphics",
                "Installing pinned DXVK-macOS DLLs...",
                lambda: install_dxvk(
                    bottle=bottle,
                    dxvk_source=graphics_source,
                    dxvk_flavor="macos",
                    without_dxgi=True,
                ),
            )
            verification = verify_dxvk_macos_profile(bottle)
            failed = [check for check in verification if check["status"] != "ok"]
            if failed:
                raise RuntimeError("DXVK-macOS verification failed: " + "; ".join(check["detail"] for check in failed))
            steps.append({"name": "verify-graphics", "status": "ok"})
            run_step(
                "probe-vulkan-d3d11",
                "Creating Vulkan and D3D11 devices and confirming the selected GPU...",
                lambda: probe_dxvk_macos_graphics(bottle=bottle, wine_path=wine64),
            )
        else:
            steps.append({"name": "install-graphics", "status": "ok"})
        if _stream_enabled(args):
            _stream_step(action=action, job_id=job_id or uuid.uuid4().hex, name="attach-libraries", status="started", message="Attaching existing Steam libraries...")
        attachment = attach_registered_libraries(bottle, refresh_registry(bottle))
        steps.append({"name": "attach-libraries", "status": "ok"})
        if graphics_backend == "d3dmetal":
            run_step(
                "verify-steam-stability",
                "Verifying Steam stability with the pinned D3DMetal engine...",
                lambda: probe_steam_stability(
                    bottle=bottle,
                    wine64_path=wine64,
                    graphics_source=graphics_source,
                ),
            )
        elif graphics_backend == "dxvk":
            run_step(
                "verify-steam-stability",
                "Updating Steam and verifying continuous DXVK-macOS stability...",
                lambda: probe_steam_stability(
                    bottle=bottle,
                    wine64_path=wine64,
                    graphics_source=graphics_source,
                    graphics_backend="dxvk",
                ),
            )
        manifest = mark_profile_ready(bottle)
    except Exception as exc:
        message = str(exc)
        if _stream_enabled(args):
            _stream_result(
                action=action,
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=message,
                data={"profile_id": profile_id, "bottle": bottle.name, "steps": steps},
                errors=[message],
            )
            raise SystemExit(1)
        _json_error(args, action=action, message=message, code=1)

    message = f"{manifest['profile']['name']} is ready in {bottle.name}."
    data = {"profile": manifest["profile"], "bottle": bottle.name, "manifest": manifest, "steps": steps, "library_attachment": attachment}
    if _stream_enabled(args):
        _stream_result(action=action, job_id=job_id or uuid.uuid4().hex, ok=True, status="completed", message=message, data=data)
    elif _json_enabled(args):
        _emit_json(action=action, ok=True, message=message, data=data)
    else:
        print(message)


def cmd_reset_compatibility_profile(args: argparse.Namespace) -> None:
    action = "reset-compatibility-profile"
    bottle = _resolve_bottle(args)
    if _is_external_prefix(args):
        _json_error(args, action=action, message="Only managed profile bottles can be reset.")
    profile = PROFILES.get(args.profile)
    if profile is None:
        _json_error(args, action=action, message=f"Unknown compatibility profile: {args.profile}")
    expected_suffix = f"-{profile.bottle_suffix}"
    if not bottle.name.endswith(expected_suffix):
        _json_error(
            args,
            action=action,
            message=f"Refusing to reset {bottle.name}; the {profile.name} bottle must end in {expected_suffix}.",
        )
    if not args.confirm:
        _json_error(args, action=action, message="Reset requires explicit confirmation.")
    if not bottle.root.exists():
        message = f"{profile.name} is already reset."
    else:
        wine64 = _require_wine64(args)
        kill_wine_processes(bottle=bottle, wine64_path=wine64)
        shutil.rmtree(bottle.root)
        message = f"Removed the dedicated {profile.name} bottle. Shared Steam game files were not removed."
    data = {"profile": args.profile, "bottle": bottle.name, "removed": not bottle.root.exists()}
    if _stream_enabled(args):
        job_id = _stream_start(action=action, message=message)
        _stream_result(action=action, job_id=job_id, ok=True, status="completed", message=message, data=data)
    elif _json_enabled(args):
        _emit_json(action=action, ok=True, message=message, data=data)
    else:
        print(message)


def cmd_attach_steam_library(args: argparse.Namespace) -> None:
    action = "attach-steam-library"
    bottle = _resolve_bottle(args)
    if _is_external_prefix(args):
        _json_error(args, action=action, message="Shared libraries can only be attached to a managed profile bottle.")
    library_ids = set(args.library_id or [])
    if not args.all and not library_ids:
        _json_error(args, action=action, message="Choose --all or provide at least one --library-id.")
    job_id = _stream_start(action=action, message=f"Attaching shared Steam libraries to {bottle.name}...") if _stream_enabled(args) else None
    try:
        registry = refresh_registry(bottle)
        result = attach_registered_libraries(bottle, registry, library_ids=None if args.all else library_ids)
        refreshed = refresh_registry(bottle)
    except RuntimeError as exc:
        message = str(exc)
        if _stream_enabled(args):
            _stream_result(action=action, job_id=job_id or uuid.uuid4().hex, ok=False, status="failed", message=message, errors=[message])
            raise SystemExit(1)
        _json_error(args, action=action, message=message, code=1)
    count = len(result["attached"])
    message = f"Attached {count} shared Steam library location(s) to {bottle.name}." if count else f"All selected Steam libraries are already attached to {bottle.name}."
    data = {**result, "registry_path": str(app_support_root() / "steam-libraries.json"), "library_count": len(refreshed["libraries"])}
    if _stream_enabled(args):
        _stream_result(action=action, job_id=job_id or uuid.uuid4().hex, ok=True, status="completed", message=message, data=data)
    elif _json_enabled(args):
        _emit_json(action=action, ok=True, message=message, data=data)
    else:
        print(message)


def cmd_init(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    ensure_bottle_dirs(bottle)
    print(f"Initializing {_target_label(args, bottle)} at: {bottle.prefix}")
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
    bottle = _resolve_bottle(args)
    print(f"Installing Steam into {_target_label(args, bottle)}...")
    code, tail = install_steam(bottle=bottle, wine64_path=wine64)
    if code != 0:
        raise SystemExit(f"Steam installer failed (exit {code}). Tail:\n{tail}")
    print("Steam install finished (or installer exited).")


def cmd_run_steam(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    registry = refresh_registry(bottle)
    acquired_library_ids: list[str] = []
    try:
        for library in registry.get("libraries", []):
            library_id = str(library.get("library_id") or "")
            references = library.get("referenced_by") or []
            attached_here = any(str(reference.get("prefix") or "") == str(bottle.prefix) for reference in references)
            if not library.get("exists") or not library_id or not attached_here:
                continue
            acquire_steam_activity(
                library_id=library_id,
                prefix=str(bottle.prefix),
                bottle=bottle.name,
                profile_id=f"steam-{bottle.name}",
                appid="*",
            )
            acquired_library_ids.append(library_id)
    except Exception:
        # Keep successful reservations: they may belong to a concurrent launch
        # in this same prefix. Unused reservations expire after the short launch window.
        raise
    mark_steam_opened_by_user(str(bottle.prefix))
    job_id = _stream_start(action="run-steam", message=f"Launching Steam in {_target_label(args, bottle)}...") if _stream_enabled(args) else None
    if not _json_enabled(args):
        print(f"Launching Steam in {_target_label(args, bottle)}...")
    code, tail = run_steam(
        bottle=bottle,
        wine64_path=wine64,
        steam_path=args.steam_path,
        extra_args=["steam://open/main"],
        wait=not args.no_wait,
        graphics_backend=_resolved_graphics_backend(args, for_steam=True),
        restart_existing=not steam_is_running(str(bottle.prefix)),
    )
    if code != 0:
        if not steam_is_running(str(bottle.prefix)):
            for library_id in acquired_library_ids:
                release_steam_activity(library_id=library_id, prefix=str(bottle.prefix))
        if _stream_enabled(args):
            _stream_result(
                action="run-steam",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"Steam launch failed (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "tail": tail},
                errors=[f"Steam launch failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="run-steam", message=f"Steam launch failed (exit {code}). Tail:\n{tail}", code=code)
    if args.no_wait:
        if _stream_enabled(args):
            _stream_result(
                action="run-steam",
                job_id=job_id or uuid.uuid4().hex,
                ok=True,
                status="started",
                message="Steam launched.",
                data={"target": _target_label(args, bottle), "tail": tail},
            )
            return
        if _json_enabled(args):
            _emit_json(
                action="run-steam",
                ok=True,
                message="Steam launched.",
                data={"target": _target_label(args, bottle), "tail": tail},
                status="started",
            )
        else:
            print("Steam launched.")
    else:
        for library_id in acquired_library_ids:
            release_steam_activity(library_id=library_id, prefix=str(bottle.prefix))
        if _stream_enabled(args):
            _stream_result(
                action="run-steam",
                job_id=job_id or uuid.uuid4().hex,
                ok=True,
                status="completed",
                message="Steam exited.",
                data={"target": _target_label(args, bottle), "tail": tail},
            )
            return
        if _json_enabled(args):
            _emit_json(
                action="run-steam",
                ok=True,
                message="Steam exited.",
                data={"target": _target_label(args, bottle), "tail": tail},
            )
        else:
            print("Steam exited.")


def cmd_winecfg(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    job_id = _stream_start(action="winecfg", message=f"Opening winecfg for {_target_label(args, bottle)}...") if _stream_enabled(args) else None
    if not _json_enabled(args):
        print(f"Opening winecfg for {_target_label(args, bottle)}...")

    code, tail = run_logged(
        cmd=[str(wine64), "winecfg"],
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / "05_winecfg.log",
    )
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="winecfg",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"winecfg failed (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "tail": tail},
                errors=[f"winecfg failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="winecfg", message=f"winecfg failed (exit {code}). Tail:\n{tail}", code=code)

    if _stream_enabled(args):
        _stream_result(
            action="winecfg",
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="completed",
            message="winecfg exited.",
            data={"target": _target_label(args, bottle), "tail": tail},
        )
        return
    if _json_enabled(args):
        _emit_json(
            action="winecfg",
            ok=True,
            message="winecfg exited.",
            data={"target": _target_label(args, bottle), "tail": tail},
            status="completed",
        )
        return
    print("winecfg exited.")


def cmd_run_winetricks(args: argparse.Namespace) -> None:
    bottle = _resolve_bottle(args)
    winetricks = resolve_executable(args.winetricks, "winetricks")
    verbs = [verb.strip() for verb in args.verbs.split(",") if verb.strip()]
    if not verbs:
        _json_error(args, action="winetricks", message="At least one winetricks verb is required")
    job_id = _stream_start(action="winetricks", message=f"Running winetricks for {', '.join(verbs)}...") if _stream_enabled(args) else None
    code, tail = run_winetricks(bottle=bottle, winetricks_path=winetricks, verbs=verbs, unattended=not args.interactive)
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="winetricks",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"winetricks failed (exit {code}). Tail:\n{tail}",
                data={"verbs": verbs, "target": _target_label(args, bottle), "tail": tail},
                errors=[f"winetricks failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="winetricks", message=f"winetricks failed (exit {code}). Tail:\n{tail}", code=code)
    if _stream_enabled(args):
        _stream_result(
            action="winetricks",
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="completed",
            message="Winetricks finished.",
            data={"verbs": verbs, "target": _target_label(args, bottle), "tail": tail},
        )
        return
    if _json_enabled(args):
        _emit_json(
            action="winetricks",
            ok=True,
            message="Winetricks finished.",
            data={"verbs": verbs, "target": _target_label(args, bottle), "tail": tail},
            status="completed",
        )


def cmd_kill_wine(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    job_id = _stream_start(action="kill-wine", message=f"Killing Wine processes for {_target_label(args, bottle)}...") if _stream_enabled(args) else None
    if not _json_enabled(args):
        print(f"Killing Wine processes for {_target_label(args, bottle)}...")

    code, tail = kill_wine_processes(bottle=bottle, wine64_path=wine64)
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="kill-wine",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"Failed to stop Wine processes (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "tail": tail},
                errors=[f"Failed to stop Wine processes (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="kill-wine", message=f"Failed to stop Wine processes (exit {code}). Tail:\n{tail}", code=code)

    if _stream_enabled(args):
        _stream_result(
            action="kill-wine",
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="completed",
            message="Stopped Wine processes.",
            data={"target": _target_label(args, bottle), "tail": tail},
        )
        return
    if _json_enabled(args):
        _emit_json(
            action="kill-wine",
            ok=True,
            message="Stopped Wine processes.",
            data={"target": _target_label(args, bottle), "tail": tail},
            status="completed",
        )
        return
    print("Stopped Wine processes.")


def cmd_list_sessions(args: argparse.Namespace) -> None:
    sessions = reconcile_sessions()
    active_only = not getattr(args, "all", False)
    if active_only:
        sessions = [session for session in sessions if session.get("status") in {"launching", "running", "stopping"}]
    if _stream_enabled(args):
        job_id = _stream_start(action="list-sessions", message="Reconciling launch sessions...")
        _stream_result(
            action="list-sessions",
            job_id=job_id,
            ok=True,
            status="completed",
            message=f"Found {len(sessions)} launch session(s).",
            data={"sessions": sessions},
        )
        return
    if _json_enabled(args):
        _emit_json(action="list-sessions", ok=True, message="Launch sessions reconciled.", data={"sessions": sessions})
        return
    for session in sessions:
        print(f"{session.get('session_id')}\t{session.get('status')}\t{session.get('game')}\t{session.get('bottle')}")


def cmd_stop_game(args: argparse.Namespace) -> None:
    job_id = _stream_start(action="stop-game", message="Stopping game...") if _stream_enabled(args) else None
    session, pids = stop_session(args.session_id)
    if session is None:
        _json_error(args, action="stop-game", message=f"Unknown launch session: {args.session_id}")
    message = session.get("message") or "Game stopped."
    data = {"session": session, "stopped_pids": pids}
    if _stream_enabled(args):
        _stream_result(
            action="stop-game",
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="completed",
            message=message,
            data=data,
        )
        return
    if _json_enabled(args):
        _emit_json(action="stop-game", ok=True, message=message, data=data)
        return
    print(message)


def cmd_install_dxvk(args: argparse.Namespace) -> None:
    bottle = _resolve_bottle(args)
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
    bottle = _resolve_bottle(args)
    wine64 = _require_wine64(args)
    code, tail = install_dxmt(
        bottle=bottle,
        dxmt_source=Path(args.dxmt_source),
        wine64_path=wine64,
        allow_unrecommended=getattr(args, "allow_unrecommended_dxmt", False),
    )
    if code != 0:
        raise SystemExit(f"DXMT install failed (exit {code}). Tail:\n{tail}")


def cmd_install_d3dmetal(args: argparse.Namespace) -> None:
    bottle = _resolve_bottle(args)
    wine64 = _require_wine64(args)
    code, tail = install_d3dmetal(
        bottle=bottle,
        d3dmetal_source=Path(args.d3dmetal_source),
        wine64_path=wine64,
    )
    if code != 0:
        raise SystemExit(f"D3DMetal install failed (exit {code}). Tail:\n{tail}")


def cmd_list_runtime_catalog(args: argparse.Namespace) -> None:
    catalog = list_runtime_catalog()
    if _json_enabled(args) or _stream_enabled(args):
        _emit_json(
            action="list-runtime-catalog",
            ok=True,
            message="Runtime catalog listed.",
            data={"runtimes": catalog},
        )
        return

    for item in catalog:
        installed = "installed" if item.get("installed") else "available"
        print(f"{item['id']}\t{item['kind']}\t{item['name']}\t{item['version']}\t{installed}")


def cmd_list_installed_runtimes(args: argparse.Namespace) -> None:
    runtimes = [runtime.__dict__ for runtime in list_installed_runtimes()]
    if _json_enabled(args) or _stream_enabled(args):
        _emit_json(
            action="list-installed-runtimes",
            ok=True,
            message="Installed runtimes listed.",
            data={"runtimes": runtimes},
        )
        return

    if not runtimes:
        print("No managed runtimes installed.")
        return
    for runtime in runtimes:
        print(f"{runtime['id']}\t{runtime['kind']}\t{runtime['name']}\t{runtime['version']}\t{runtime['path']}")


def cmd_install_runtime(args: argparse.Namespace) -> None:
    bottle = _resolve_bottle(args)
    wine_path = None
    if args.wine or args.wine64:
        wine_path = _require_wine64(args)
    action = "install-runtime"
    job_id = _stream_start(action=action, message=f"Installing runtime {args.runtime}...") if _stream_enabled(args) else None

    def callback(name: str, status: str, message: str) -> None:
        if _stream_enabled(args):
            _stream_step(
                action=action,
                job_id=job_id or uuid.uuid4().hex,
                name=name,
                status=status,
                message=message,
            )

    try:
        installed, notes = install_runtime(
            runtime_id=args.runtime,
            bottle=bottle,
            wine_path=wine_path,
            install_into_bottle=not args.no_bottle_install,
            callback=callback,
        )
    except Exception as exc:
        message = str(exc)
        if _stream_enabled(args):
            _stream_result(
                action=action,
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=message,
                errors=[message],
            )
            raise SystemExit(1)
        _json_error(args, action=action, message=message, code=1)

    data = {"runtime": installed.__dict__, "notes": notes}
    message = f"Installed {installed.name} {installed.version}."
    if _stream_enabled(args):
        _stream_result(
            action=action,
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="completed",
            message=message,
            data=data,
        )
        return
    if _json_enabled(args):
        _emit_json(action=action, ok=True, message=message, data=data)
        return
    print(message)
    for note in notes:
        print(note)


def cmd_setup_metal(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    ensure_bottle_dirs(bottle)
    job_id = _stream_start(action="setup-metal", message=f"Starting Metal setup for {_target_label(args, bottle)}...") if _stream_enabled(args) else None
    total_steps = 4 if args.no_launch else 5
    runtime = detect_wine_runtime(wine64)
    steps: list[dict[str, str]] = []

    app_name = runtime.get("app_name") or "unknown Wine app"
    version_output = runtime.get("version_output") or "unknown version"
    if not _json_enabled(args):
        print(f"Detected Wine runtime: {app_name} ({version_output})")
        if not runtime.get("is_stable_11"):
            print("Note: the Metal setup is tuned for Wine Stable 11.0.")
            print("      This runtime may still work, but if setup-metal or Steam behaves oddly,")
            print("      switch to /Applications/Wine Stable.app before debugging the prefix.")

    if _is_external_prefix(args):
        if not _json_enabled(args):
            print(f"Using external prefix: {bottle.prefix}")
            print(f"Support files will still live under: {bottle.root}")
    else:
        if not _json_enabled(args):
            print(f"Using managed bottle '{bottle.name}'")
            print(f"Managed prefix path: {bottle.prefix}")

    if not _json_enabled(args):
        print("Initializing prefix...")
    if _stream_enabled(args):
        _stream_step(action="setup-metal", job_id=job_id or uuid.uuid4().hex, name="wineboot", status="started", message="Initializing prefix...")
    code, tail = run_logged(
        cmd=[str(wine64), "wineboot", "-u"],
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / "01_wineboot.log",
    )
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"wineboot failed (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail},
                errors=[f"wineboot failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="setup-metal", message=f"wineboot failed (exit {code}). Tail:\n{tail}", code=code)
    steps.append({"name": "wineboot", "status": "ok"})
    if _stream_enabled(args):
        _stream_progress(
            action="setup-metal",
            job_id=job_id or uuid.uuid4().hex,
            name="wineboot",
            status="ok",
            message="Initialized prefix.",
            completed_steps=1,
            total_steps=total_steps,
        )

    if not _json_enabled(args):
        print("Setting the prefix Windows version to Windows 10...")
    if _stream_enabled(args):
        _stream_step(action="setup-metal", job_id=job_id or uuid.uuid4().hex, name="set-win10", status="started", message="Setting Windows version to Windows 10...")
    code, tail = set_prefix_windows_version(bottle, wine64, "win10")
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"winecfg -v win10 failed (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail},
                errors=[f"winecfg -v win10 failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="setup-metal", message=f"winecfg -v win10 failed (exit {code}). Tail:\n{tail}", code=code)
    steps.append({"name": "set-win10", "status": "ok"})
    if _stream_enabled(args):
        _stream_progress(
            action="setup-metal",
            job_id=job_id or uuid.uuid4().hex,
            name="set-win10",
            status="ok",
            message="Set Windows version to Windows 10.",
            completed_steps=2,
            total_steps=total_steps,
        )

    winetricks = resolve_executable(args.winetricks, "winetricks")
    if not _json_enabled(args):
        print("Installing Steam via winetricks...")
    if _stream_enabled(args):
        _stream_step(action="setup-metal", job_id=job_id or uuid.uuid4().hex, name="winetricks-steam", status="started", message="Installing Steam via winetricks...")
    code, tail = run_winetricks(
        bottle=bottle,
        winetricks_path=winetricks,
        verbs=["steam"],
        log_name="02_winetricks_steam.log",
        unattended=not args.interactive,
    )
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"winetricks steam failed (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail},
                errors=[f"winetricks steam failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="setup-metal", message=f"winetricks steam failed (exit {code}). Tail:\n{tail}", code=code)
    steps.append({"name": "winetricks-steam", "status": "ok"})
    if _stream_enabled(args):
        _stream_progress(
            action="setup-metal",
            job_id=job_id or uuid.uuid4().hex,
            name="winetricks-steam",
            status="ok",
            message="Installed Steam via winetricks.",
            completed_steps=3,
            total_steps=total_steps,
        )

    if not _json_enabled(args):
        print("Installing DXMT into the Wine runtime and prefix...")
    if _stream_enabled(args):
        _stream_step(action="setup-metal", job_id=job_id or uuid.uuid4().hex, name="install-dxmt", status="started", message="Installing DXMT...")
    code, tail = install_dxmt(
        bottle=bottle,
        dxmt_source=Path(args.dxmt_source),
        wine64_path=wine64,
        allow_unrecommended=getattr(args, "allow_unrecommended_dxmt", False),
    )
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"DXMT install failed (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail},
                errors=[f"DXMT install failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="setup-metal", message=f"DXMT install failed (exit {code}). Tail:\n{tail}", code=code)
    steps.append({"name": "install-dxmt", "status": "ok"})
    if _stream_enabled(args):
        _stream_progress(
            action="setup-metal",
            job_id=job_id or uuid.uuid4().hex,
            name="install-dxmt",
            status="ok",
            message="Installed DXMT.",
            completed_steps=4,
            total_steps=total_steps,
        )

    if args.no_launch:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=True,
                status="completed",
                message="Metal setup complete.",
                data={"target": _target_label(args, bottle), "steps": steps, "completed_steps": total_steps, "total_steps": total_steps, "progress": 1.0},
            )
            return
        if _json_enabled(args):
            _emit_json(
                action="setup-metal",
                ok=True,
                message="Metal setup complete.",
                data={"target": _target_label(args, bottle), "steps": steps},
                status="completed",
            )
        else:
            print("Metal setup complete.")
            if _is_external_prefix(args):
                print("Next step:")
                print(f"python3 mysteamwine.py --prefix {bottle.prefix} --wine {wine64} run-steam")
            else:
                print("Next step:")
                print(f"python3 mysteamwine.py --bottle {bottle.name} --wine {wine64} run-steam")
        return

    if not _json_enabled(args):
        print("Opening Steam...")
    if _stream_enabled(args):
        _stream_step(action="setup-metal", job_id=job_id or uuid.uuid4().hex, name="run-steam", status="started", message="Opening Steam...")
    code, tail = run_steam(
        bottle=bottle,
        wine64_path=wine64,
        wait=not args.no_wait,
        graphics_backend=_resolved_graphics_backend(args, for_steam=True),
    )
    if code != 0:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"Steam launch failed after setup (exit {code}). Tail:\n{tail}",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail},
                errors=[f"Steam launch failed after setup (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="setup-metal", message=f"Steam launch failed after setup (exit {code}). Tail:\n{tail}", code=code)
    steps.append({"name": "run-steam", "status": "ok"})
    if _stream_enabled(args):
        _stream_progress(
            action="setup-metal",
            job_id=job_id or uuid.uuid4().hex,
            name="run-steam",
            status="ok",
            message="Steam opened.",
            completed_steps=5,
            total_steps=total_steps,
        )
    if args.no_wait:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=True,
                status="started",
                message="Metal setup complete. Steam launched.",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail, "completed_steps": total_steps, "total_steps": total_steps, "progress": 1.0},
            )
            return
        if _json_enabled(args):
            _emit_json(
                action="setup-metal",
                ok=True,
                message="Metal setup complete. Steam launched.",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail},
                status="started",
            )
        else:
            print("Metal setup complete. Steam launched.")
    else:
        if _stream_enabled(args):
            _stream_result(
                action="setup-metal",
                job_id=job_id or uuid.uuid4().hex,
                ok=True,
                status="completed",
                message="Metal setup complete. Steam exited.",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail, "completed_steps": total_steps, "total_steps": total_steps, "progress": 1.0},
            )
            return
        if _json_enabled(args):
            _emit_json(
                action="setup-metal",
                ok=True,
                message="Metal setup complete. Steam exited.",
                data={"target": _target_label(args, bottle), "steps": steps, "tail": tail},
                status="completed",
            )
        else:
            print("Metal setup complete. Steam exited.")


def cmd_wipe_bottles(args: argparse.Namespace) -> None:
    if not args.yes:
        raise SystemExit("Refusing to wipe all bottles without --yes")
    removed = wipe_all_bottles()
    if not removed:
        print("No bottles found.")
        return
    print(f"Removed {len(removed)} bottle(s):")
    for bottle_root in removed:
        print(bottle_root)


def cmd_list_games(args: argparse.Namespace) -> None:
    bottle = _resolve_bottle(args)
    job_id = _stream_start(action="list-games", message="Scanning registered Steam libraries...") if _stream_enabled(args) else None
    registry = refresh_registry(bottle)
    games = installed_games(registry)
    data = {
        "target": _target_label(args, bottle),
        "registry_path": str(app_support_root() / "steam-libraries.json"),
        "library_count": len(registry["libraries"]),
        "libraries": registry["libraries"],
        "games": games,
    }
    message = f"Found {len(games)} installed Steam game(s) across {len(registry['libraries'])} library location(s)." if games else "No installed Steam games were found in registered libraries."
    if _stream_enabled(args):
        _stream_result(
            action="list-games",
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="completed",
            message=message,
            data=data,
            warnings=registry["warnings"],
        )
        return
    if _json_enabled(args):
        _emit_json(
            action="list-games",
            ok=True,
            message=message,
            data=data,
            warnings=registry["warnings"],
            status="completed",
        )
        return
    if not games:
        print(message)
        return
    for game in games:
        print(f"{game['appid']}\t{game['name']}\t{game['install_dir']}")


def cmd_doctor(args: argparse.Namespace) -> None:
    bottle = _resolve_bottle(args)
    wine_value = args.wine64 or args.wine
    actions: list[str] = []
    job_id = _stream_start(action="doctor", message=f"Running doctor for {_target_label(args, bottle)}...") if _stream_enabled(args) else None
    if args.fix:
        if _stream_enabled(args):
            _stream_step(action="doctor", job_id=job_id or uuid.uuid4().hex, name="doctor-fix", status="started", message="Applying safe fixes...")
        try:
            actions = apply_doctor_fixes(
                bottle=bottle,
                wine_value=wine_value,
                dxmt_source=args.dxmt_source,
                allow_unrecommended_dxmt=getattr(args, "allow_unrecommended_dxmt", False),
            )
        except Exception as exc:
            if _stream_enabled(args):
                _stream_result(
                    action="doctor",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"doctor --fix failed: {exc}",
                    errors=[f"doctor --fix failed: {exc}"],
                )
                raise SystemExit(1)
            _json_error(args, action="doctor", message=f"doctor --fix failed: {exc}")
        if not _json_enabled(args):
            print(f"Doctor fix target: {_target_label(args, bottle)}")
            for action in actions:
                print(f"[FIX ] {action}")
        if _stream_enabled(args):
            _stream_step(action="doctor", job_id=job_id or uuid.uuid4().hex, name="doctor-fix", status="ok", message="Applied safe fixes.")

    results = run_doctor(bottle=bottle, wine_value=wine_value, winetricks_value=args.winetricks)

    worst_status = "ok"
    rank = {"ok": 0, "warn": 1, "fail": 2}
    checks_payload = []
    for result in results:
        checks_payload.append({"status": result.status, "name": result.name, "detail": result.detail})
        if rank[result.status] > rank[worst_status]:
            worst_status = result.status

    if _stream_enabled(args):
        _stream_result(
            action="doctor",
            job_id=job_id or uuid.uuid4().hex,
            ok=worst_status != "fail",
            status="failed" if worst_status == "fail" else "completed",
            message=f"Doctor finished with status {worst_status}.",
            data={
                "target": _target_label(args, bottle),
                "worst_status": worst_status,
                "checks": checks_payload,
                "actions": actions,
            },
            errors=[] if worst_status != "fail" else ["One or more checks failed."],
        )
        if worst_status == "fail":
            raise SystemExit(1)
        return

    if _json_enabled(args):
        _emit_json(
            action="doctor",
            ok=worst_status != "fail",
            message=f"Doctor finished with status {worst_status}.",
            data={
                "target": _target_label(args, bottle),
                "worst_status": worst_status,
                "checks": checks_payload,
                "actions": actions,
            },
            errors=[] if worst_status != "fail" else ["One or more checks failed."],
            status="failed" if worst_status == "fail" else "completed",
        )
        if worst_status == "fail":
            raise SystemExit(1)
        return

    print(f"Doctor target: {_target_label(args, bottle)}")
    for result in results:
        print(f"[{result.status.upper():4}] {result.name}: {result.detail}")

    if worst_status == "fail":
        raise SystemExit(1)


def cmd_launch_game(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    app, library_id = resolve_registered_app(bottle, args.appid)
    graphics_backend = _resolved_graphics_backend(args, for_steam=False)
    profile_id = _bind_launch_profile(
        args, action="launch-game", bottle=bottle, wine_path=wine64, graphics_backend=graphics_backend
    )
    job_id = _stream_start(action="launch-game", message=f"Launching {app.name} ({app.appid})...") if _stream_enabled(args) else None
    if not _json_enabled(args):
        print(f"Launching {app.name} ({app.appid}) via Steam.")
    if graphics_backend == "dxmt" and args.dxmt_source:
        code, tail = install_dxmt(
            bottle=bottle,
            dxmt_source=Path(args.dxmt_source),
            wine64_path=wine64,
            allow_unrecommended=getattr(args, "allow_unrecommended_dxmt", False),
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"DXMT restore failed (exit {code}). Tail:\n{tail}",
                    data={"appid": app.appid, "name": app.name, "tail": tail},
                    errors=[f"DXMT restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="launch-game", message=f"DXMT restore failed (exit {code}). Tail:\n{tail}", code=code)
    elif graphics_backend == "dxvk" and args.dxvk_source:
        code, tail = install_dxvk(
            bottle=bottle,
            dxvk_source=Path(args.dxvk_source),
            dxvk_flavor=args.dxvk_flavor,
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"DXVK restore failed (exit {code}). Tail:\n{tail}",
                    data={"appid": app.appid, "name": app.name, "tail": tail},
                    errors=[f"DXVK restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="launch-game", message=f"DXVK restore failed (exit {code}). Tail:\n{tail}", code=code)
    elif graphics_backend == "d3dmetal" and args.d3dmetal_source:
        code, tail = install_d3dmetal(
            bottle=bottle,
            d3dmetal_source=Path(args.d3dmetal_source),
            wine64_path=wine64,
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"D3DMetal restore failed (exit {code}). Tail:\n{tail}",
                    data={"appid": app.appid, "name": app.name, "tail": tail},
                    errors=[f"D3DMetal restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="launch-game", message=f"D3DMetal restore failed (exit {code}). Tail:\n{tail}", code=code)
    try:
        executable_hint = guess_game_executable(app.install_dir)
    except (FileNotFoundError, RuntimeError):
        executable_hint = None
    steam_was_running = steam_is_running(str(bottle.prefix))
    acquire_steam_activity(
        library_id=library_id,
        prefix=str(bottle.prefix),
        bottle=bottle.name,
        profile_id=profile_id,
        appid=app.appid,
    )
    launch_session = create_session(
        bottle=bottle,
        appid=app.appid,
        game=app.name,
        executable=executable_hint,
        install_dir=app.install_dir,
        graphics_backend=graphics_backend,
        strategy="steam",
        profile_id=profile_id,
        wine_path=wine64,
        steam_started_by_nase=not steam_was_running,
        steam_was_running=steam_was_running,
        library_id=library_id,
    )
    code, tail = launch_app(
        bottle=bottle,
        wine64_path=wine64,
        appid=args.appid,
        graphics_backend=graphics_backend,
        wait=not args.no_wait,
        restart_existing=not steam_was_running,
        graphics_source=Path(args.d3dmetal_source) if graphics_backend == "d3dmetal" and args.d3dmetal_source else None,
    )
    if code != 0:
        if not steam_is_running(str(bottle.prefix)):
            release_steam_activity(library_id=library_id, prefix=str(bottle.prefix))
        update_session(
            launch_session["session_id"],
            status="failed",
            message="Steam launch failed.",
            steam_cleanup_after=time.time() + 10 if launch_session.get("steam_started_by_nase") else None,
        )
        if _stream_enabled(args):
            _stream_result(
                action="launch-game",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"App launch failed (exit {code}). Tail:\n{tail}",
                data={"appid": app.appid, "name": app.name, "tail": tail},
                errors=[f"App launch failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="launch-game", message=f"App launch failed (exit {code}). Tail:\n{tail}", code=code)
    launch_session = next(
        (item for item in reconcile_sessions() if item.get("session_id") == launch_session["session_id"]),
        launch_session,
    )
    if args.no_wait:
        if _stream_enabled(args):
            _stream_result(
                action="launch-game",
                job_id=job_id or uuid.uuid4().hex,
                ok=True,
                status="started",
                message="Launch request sent.",
                data={"appid": app.appid, "name": app.name, "tail": tail, "session": launch_session},
            )
            return
        if _json_enabled(args):
            _emit_json(
                action="launch-game",
                ok=True,
                message="Launch request sent.",
                data={"appid": app.appid, "name": app.name, "tail": tail, "session": launch_session},
                status="started",
            )
        else:
            print("Launch request sent.")


def cmd_smart_launch_game(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    graphics_backend = _resolved_graphics_backend(args, for_steam=False)
    profile_id = _bind_launch_profile(
        args, action="smart-launch-game", bottle=bottle, wine_path=wine64, graphics_backend=graphics_backend
    )
    try:
        app, library_id = resolve_registered_app(bottle, args.appid)
    except FileNotFoundError:
        if graphics_backend != "d3dmetal":
            raise
        app = None
        library_id = ""
    app_name = app.name if app else f"Steam App {args.appid}"
    job_id = _stream_start(action="smart-launch-game", message=f"Launching {app_name} ({args.appid})...") if _stream_enabled(args) else None

    if graphics_backend == "d3dmetal":
        steam_exe = bottle.drive_c / "Program Files (x86)" / "Steam" / "Steam.exe"
        if not steam_exe.exists():
            if _stream_enabled(args):
                _stream_step(
                    action="smart-launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    name="setup-d3dmetal-steam",
                    status="started",
                    message="Preparing hidden D3DMetal Steam environment...",
                )
            setup_steps = (
                ("wineboot", lambda: run_logged(
                    cmd=[str(wine64), "wineboot", "-u"],
                    env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
                    log_file=bottle.logs / "01_wineboot_d3dmetal.log",
                    timeout=60,
                )),
                ("set-win10", lambda: set_prefix_windows_version(bottle, wine64, "win10")),
                ("winetricks-steam", lambda: run_winetricks(
                    bottle=bottle,
                    winetricks_path=resolve_executable(getattr(args, "winetricks", "winetricks"), "winetricks"),
                    verbs=["steam"],
                    log_name="02_winetricks_steam_d3dmetal.log",
                    unattended=True,
                )),
            )
            for step_name, step in setup_steps:
                code, tail = step()
                if code != 0:
                    message = f"D3DMetal environment setup failed at {step_name} (exit {code}). Tail:\n{tail}"
                    if _stream_enabled(args):
                        _stream_result(
                            action="smart-launch-game",
                            job_id=job_id or uuid.uuid4().hex,
                            ok=False,
                            status="failed",
                            message=message,
                            data={"appid": args.appid, "name": app_name, "tail": tail},
                            errors=[message],
                        )
                        raise SystemExit(code)
                    _json_error(args, action="smart-launch-game", message=message, code=code)
            if _stream_enabled(args):
                _stream_step(
                    action="smart-launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    name="setup-d3dmetal-steam",
                    status="ok",
                    message="Prepared hidden D3DMetal Steam environment.",
                )

    if graphics_backend == "dxmt" and args.dxmt_source:
        code, tail = install_dxmt(
            bottle=bottle,
            dxmt_source=Path(args.dxmt_source),
            wine64_path=wine64,
            allow_unrecommended=getattr(args, "allow_unrecommended_dxmt", False),
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="smart-launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"DXMT restore failed (exit {code}). Tail:\n{tail}",
                    data={"appid": args.appid, "name": app_name, "tail": tail},
                    errors=[f"DXMT restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="smart-launch-game", message=f"DXMT restore failed (exit {code}). Tail:\n{tail}", code=code)
    elif graphics_backend == "dxvk" and args.dxvk_source:
        code, tail = install_dxvk(
            bottle=bottle,
            dxvk_source=Path(args.dxvk_source),
            dxvk_flavor=args.dxvk_flavor,
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="smart-launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"DXVK restore failed (exit {code}). Tail:\n{tail}",
                    data={"appid": args.appid, "name": app_name, "tail": tail},
                    errors=[f"DXVK restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="smart-launch-game", message=f"DXVK restore failed (exit {code}). Tail:\n{tail}", code=code)
    elif graphics_backend == "d3dmetal" and args.d3dmetal_source:
        code, tail = install_d3dmetal(
            bottle=bottle,
            d3dmetal_source=Path(args.d3dmetal_source),
            wine64_path=wine64,
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="smart-launch-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"D3DMetal restore failed (exit {code}). Tail:\n{tail}",
                    data={"appid": args.appid, "name": app_name, "tail": tail},
                    errors=[f"D3DMetal restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="smart-launch-game", message=f"D3DMetal restore failed (exit {code}). Tail:\n{tail}", code=code)

    direct_error: str | None = None
    skip_direct_reason: str | None = None
    executable_hint: Path | None = None
    if app is not None:
        try:
            executable_hint = guess_game_executable(app.install_dir)
        except (FileNotFoundError, RuntimeError):
            executable_hint = None
    launch_session = create_session(
        bottle=bottle,
        appid=args.appid,
        game=app_name,
        executable=executable_hint,
        install_dir=app.install_dir if app is not None else None,
        graphics_backend=graphics_backend,
        strategy="pending",
        profile_id=profile_id,
        wine_path=wine64,
        library_id=library_id,
    )
    try:
        if app is None:
            skip_direct_reason = "No manifest found in the hidden D3DMetal environment yet; using Steam protocol launch."
        else:
            scan = scan_game_dir(app.install_dir, max_files=1200)
            if any(signal.key == "unity" for signal in scan.signals):
                skip_direct_reason = "Skipped direct launch for Unity title; using Steam launch for better renderer compatibility."
    except Exception:
        scan = None

    if skip_direct_reason is None:
        try:
            assert_direct_launch_safe(library_path=app.library_path, appid=args.appid)
            executable = executable_hint or guess_game_executable(app.install_dir)
            code, tail = run_game_executable(
                bottle=bottle,
                wine64_path=wine64,
                executable=executable,
                extra_args=None,
                extra_env=None,
                cwd=executable.parent,
                wine_debug="-all",
                wait=False,
                graphics_backend=graphics_backend,
                probe_seconds=args.probe_seconds,
                graphics_source=Path(args.d3dmetal_source) if graphics_backend == "d3dmetal" and args.d3dmetal_source else None,
            )
            if code == 0:
                update_session(launch_session["session_id"], strategy="direct", message="Direct launch request sent.")
                launch_session = next(
                    (item for item in reconcile_sessions() if item.get("session_id") == launch_session["session_id"]),
                    launch_session,
                )
                message = "Direct launch started."
                data = {
                    "appid": args.appid,
                    "name": app_name,
                    "executable": str(executable),
                    "strategy": "direct",
                    "tail": tail,
                    "session": launch_session,
                }
                if _stream_enabled(args):
                    _stream_result(
                        action="smart-launch-game",
                        job_id=job_id or uuid.uuid4().hex,
                        ok=True,
                        status="started",
                        message=message,
                        data=data,
                    )
                    return
                if _json_enabled(args):
                    _emit_json(
                        action="smart-launch-game",
                        ok=True,
                        message=message,
                        data=data,
                        status="started",
                    )
                    return
                print(message)
                return
            direct_error = f"Direct launch failed (exit {code}). Tail:\n{tail}"
        except Exception as exc:
            direct_error = str(exc)
    else:
        direct_error = skip_direct_reason

    steam_was_running = steam_is_running(str(bottle.prefix))
    acquire_steam_activity(
        library_id=library_id,
        prefix=str(bottle.prefix),
        bottle=bottle.name,
        profile_id=profile_id,
        appid=args.appid,
    )
    update_session(
        launch_session["session_id"],
        steam_was_running=steam_was_running,
        steam_started_by_nase=not steam_was_running,
        steam_cleanup_status="not-owned" if steam_was_running else "pending",
    )
    code, tail = launch_app(
        bottle=bottle,
        wine64_path=wine64,
        appid=args.appid,
        graphics_backend=graphics_backend,
        wait=not args.no_wait,
        restart_existing=not steam_was_running,
        graphics_source=Path(args.d3dmetal_source) if graphics_backend == "d3dmetal" and args.d3dmetal_source else None,
    )
    if code != 0:
        if not steam_is_running(str(bottle.prefix)):
            release_steam_activity(library_id=library_id, prefix=str(bottle.prefix))
        update_session(
            launch_session["session_id"],
            status="failed",
            strategy="steam-fallback",
            message="Steam launch failed.",
            steam_cleanup_after=time.time() + 10 if not steam_was_running else None,
        )
        failure = f"Fallback Steam launch failed (exit {code}). Tail:\n{tail}"
        combined = f"{direct_error or 'Direct launch failed.'}\n\n{failure}"
        if _stream_enabled(args):
            _stream_result(
                action="smart-launch-game",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=combined,
                data={"appid": args.appid, "name": app_name, "tail": tail, "strategy": "steam-fallback", "session": launch_session},
                errors=[failure],
            )
            raise SystemExit(code)
        _json_error(args, action="smart-launch-game", message=combined, code=code)

    update_session(launch_session["session_id"], strategy="steam-fallback", message="Steam launch request sent.")
    launch_session = next(
        (item for item in reconcile_sessions() if item.get("session_id") == launch_session["session_id"]),
        launch_session,
    )
    message = "Opened with Steam after direct launch failed."
    data = {
        "appid": args.appid,
        "name": app_name,
        "strategy": "steam-fallback",
        "tail": tail,
        "warnings": [direct_error] if direct_error else [],
        "session": launch_session,
    }
    if _stream_enabled(args):
        _stream_result(
            action="smart-launch-game",
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="started" if args.no_wait else "completed",
            message=message,
            data=data,
            warnings=[direct_error] if direct_error else [],
        )
        return
    if _json_enabled(args):
        _emit_json(
            action="smart-launch-game",
            ok=True,
            message=message,
            data=data,
            warnings=[direct_error] if direct_error else [],
            status="started" if args.no_wait else "completed",
        )
        return
    print(message)


def cmd_gui(args: argparse.Namespace) -> None:
    from .gui import launch_gui

    launch_gui(args)


def _resolve_debug_executable(args: argparse.Namespace) -> Path:
    if args.exe:
        return Path(args.exe)
    if args.appid:
        bottle = _resolve_bottle(args)
        app, _ = resolve_registered_app(bottle, args.appid)
        return guess_game_executable(app.install_dir)
    raise SystemExit("Provide either --appid or --exe")


def cmd_debug_game(args: argparse.Namespace) -> None:
    wine64 = _require_wine64(args)
    bottle = _resolve_bottle(args)
    executable = _resolve_debug_executable(args)
    graphics_backend = _resolved_graphics_backend(args, for_steam=False)
    profile_id = _bind_launch_profile(
        args, action="debug-game", bottle=bottle, wine_path=wine64, graphics_backend=graphics_backend
    )
    job_id = _stream_start(action="debug-game", message=f"Launching {executable.name} with Wine debug logging...") if _stream_enabled(args) else None
    extra_args = list(args.game_args or [])
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    extra_env: dict[str, str] = {}
    for entry in args.env or []:
        if "=" not in entry:
            raise SystemExit(f"Invalid --env value: {entry!r}. Expected KEY=VALUE.")
        key, value = entry.split("=", 1)
        extra_env[key] = value

    if not _json_enabled(args):
        print(f"Launching {executable.name} directly with Wine debug logging...")
    if graphics_backend == "dxmt" and args.dxmt_source:
        code, tail = install_dxmt(
            bottle=bottle,
            dxmt_source=Path(args.dxmt_source),
            wine64_path=wine64,
            allow_unrecommended=getattr(args, "allow_unrecommended_dxmt", False),
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="debug-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"DXMT restore failed (exit {code}). Tail:\n{tail}",
                    data={"executable": str(executable), "tail": tail},
                    errors=[f"DXMT restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="debug-game", message=f"DXMT restore failed (exit {code}). Tail:\n{tail}", code=code)
    elif graphics_backend == "dxvk" and args.dxvk_source:
        code, tail = install_dxvk(
            bottle=bottle,
            dxvk_source=Path(args.dxvk_source),
            dxvk_flavor=args.dxvk_flavor,
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="debug-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"DXVK restore failed (exit {code}). Tail:\n{tail}",
                    data={"executable": str(executable), "tail": tail},
                    errors=[f"DXVK restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="debug-game", message=f"DXVK restore failed (exit {code}). Tail:\n{tail}", code=code)
    elif graphics_backend == "d3dmetal" and args.d3dmetal_source:
        code, tail = install_d3dmetal(
            bottle=bottle,
            d3dmetal_source=Path(args.d3dmetal_source),
            wine64_path=wine64,
        )
        if code != 0:
            if _stream_enabled(args):
                _stream_result(
                    action="debug-game",
                    job_id=job_id or uuid.uuid4().hex,
                    ok=False,
                    status="failed",
                    message=f"D3DMetal restore failed (exit {code}). Tail:\n{tail}",
                    data={"executable": str(executable), "tail": tail},
                    errors=[f"D3DMetal restore failed (exit {code})."],
                )
                raise SystemExit(code)
            _json_error(args, action="debug-game", message=f"D3DMetal restore failed (exit {code}). Tail:\n{tail}", code=code)
    debug_app = resolve_registered_app(bottle, args.appid)[0] if args.appid else None
    launch_session = create_session(
        bottle=bottle,
        appid=args.appid,
        game=debug_app.name if debug_app else executable.stem,
        executable=executable,
        install_dir=debug_app.install_dir if debug_app else executable.parent,
        graphics_backend=graphics_backend,
        strategy="direct",
        profile_id=profile_id,
        wine_path=wine64,
    )
    code, tail = run_game_executable(
        bottle=bottle,
        wine64_path=wine64,
        executable=executable,
        extra_args=extra_args,
        extra_env=extra_env or None,
        cwd=Path(args.cwd) if args.cwd else None,
        wine_debug=args.wine_debug,
        wait=not args.no_wait,
        graphics_backend=graphics_backend,
        graphics_source=Path(args.d3dmetal_source) if graphics_backend == "d3dmetal" and args.d3dmetal_source else None,
    )
    if code != 0:
        update_session(launch_session["session_id"], status="failed", message="Direct game launch failed.")
        if _stream_enabled(args):
            _stream_result(
                action="debug-game",
                job_id=job_id or uuid.uuid4().hex,
                ok=False,
                status="failed",
                message=f"Direct game launch failed (exit {code}). Tail:\n{tail}",
                data={"executable": str(executable), "tail": tail},
                errors=[f"Direct game launch failed (exit {code})."],
            )
            raise SystemExit(code)
        _json_error(args, action="debug-game", message=f"Direct game launch failed (exit {code}). Tail:\n{tail}", code=code)
    if not args.no_wait:
        update_session(launch_session["session_id"], status="exited", message="Game process exited.")
    launch_session = next(
        (item for item in reconcile_sessions() if item.get("session_id") == launch_session["session_id"]),
        launch_session,
    )
    if _stream_enabled(args):
        _stream_result(
            action="debug-game",
            job_id=job_id or uuid.uuid4().hex,
            ok=True,
            status="started" if args.no_wait else "completed",
            message="Game process exited." if not args.no_wait else "Debug launch started.",
            data={"executable": str(executable), "tail": tail, "session": launch_session},
        )
        return
    if _json_enabled(args):
        _emit_json(
            action="debug-game",
            ok=True,
            message="Game process exited." if not args.no_wait else "Debug launch started.",
            data={"executable": str(executable), "tail": tail, "session": launch_session},
            status="started" if args.no_wait else "completed",
        )
    else:
        print("Game process exited.")


def _resolve_scan_target(args: argparse.Namespace) -> Path:
    if args.path:
        return Path(args.path)
    if args.appid:
        bottle = _resolve_bottle(args)
        return resolve_registered_app(bottle, args.appid)[0].install_dir
    raise SystemExit("Provide either --path or --appid")


def cmd_scan_game(args: argparse.Namespace) -> None:
    scan = scan_game_dir(_resolve_scan_target(args))
    if _json_enabled(args):
        _emit_json(
            action="scan-game",
            ok=True,
            message=f"Scanned {scan.root}",
            data={
                "root": str(scan.root),
                "signals": [
                    {"key": signal.key, "detail": signal.detail, "path": str(signal.path)}
                    for signal in scan.signals
                ],
            },
            status="completed",
        )
        return
    if not scan.signals:
        print(f"No known dependency markers found in {scan.root}")
        return
    for signal in scan.signals:
        print(f"{signal.key}\t{signal.detail}\t{signal.path}")


def cmd_advise_game(args: argparse.Namespace) -> None:
    scan = scan_game_dir(_resolve_scan_target(args))
    recommendations = recommend_dependencies(scan)
    if _json_enabled(args):
        _emit_json(
            action="advise-game",
            ok=True,
            message=f"Generated {len(recommendations)} recommendation(s)." if recommendations else f"No rules matched for {scan.root}",
            data={
                "root": str(scan.root),
                "recommendations": [
                    {"verb": rec.verb, "reason": rec.reason}
                    for rec in recommendations
                ],
            },
            status="completed",
        )
        return
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
        "--prefix",
        help="Use an existing Wine prefix directly instead of a managed bottle, for example: ~/.wine-bluearchive",
    )
    parser.add_argument(
        "--wine64",
        help="Path to the Wine launcher (example: /opt/homebrew/bin/wine or /opt/homebrew/bin/wine64)",
    )
    parser.add_argument("--wine", dest="wine", help="Alias for --wine64 for compatibility with older usage")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON for app integrations")
    parser.add_argument("--jsonl", action="store_true", help="Emit streaming machine-readable JSON lines for app integrations")
    parser.add_argument(
        "--graphics-backend",
        choices=("auto", "dxvk", "dxmt", "d3dmetal", "none"),
        default="auto",
        help="Graphics backend override to apply at launch time (default: auto: plain Steam, DXMT for games)",
    )
    parser.add_argument(
        "--compatibility-profile",
        help="Pinned compatibility profile id. Defaults to the profile for --graphics-backend.",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Show paths used for this bottle").set_defaults(func=cmd_info)
    sub.add_parser("list-compatibility-profiles", help="List pinned graphics/runtime profiles").set_defaults(func=cmd_list_compatibility_profiles)
    discover_d3dmetal = sub.add_parser("discover-d3dmetal", help="Find a matched local GPTK Wine and D3DMetal installation")
    discover_d3dmetal.add_argument("--gptk-wine", help="Previously selected GPTK Wine executable")
    discover_d3dmetal.add_argument("--d3dmetal-source", help="Previously selected GPTK/D3DMetal root")
    discover_d3dmetal.set_defaults(func=cmd_discover_d3dmetal)
    import_gptk = sub.add_parser("import-gptk", help="Copy a licensed GPTK installation into NASE managed storage")
    import_gptk.add_argument("--gptk-wine", required=True, help="GPTK Wine executable")
    import_gptk.add_argument("--d3dmetal-source", required=True, help="Root of the same GPTK installation")
    import_gptk.add_argument("--confirm-license", action="store_true", help="Confirm acceptance of Apple's GPTK license")
    import_gptk.set_defaults(func=cmd_import_gptk)
    dependency_cmd = sub.add_parser("dependency-status", help="Check host dependencies required by NASE profiles")
    dependency_cmd.add_argument("--winetricks", default="winetricks", help="Path or command name for Winetricks")
    dependency_cmd.add_argument("--gptk-wine", help="Optional GPTK Wine executable")
    dependency_cmd.add_argument("--d3dmetal-source", help="Optional D3DMetal source directory")
    dependency_cmd.set_defaults(func=cmd_dependency_status)
    install_dependency_cmd = sub.add_parser("install-host-dependency", help="Install one confirmed host dependency")
    install_dependency_cmd.add_argument("--dependency", choices=("python", "rosetta", "wine-stable", "winetricks"), required=True)
    install_dependency_cmd.add_argument("--confirm-rosetta-license", action="store_true", help="Confirm acceptance of Apple's Rosetta software license")
    install_dependency_cmd.set_defaults(func=cmd_install_host_dependency)
    profile_setup = sub.add_parser("setup-compatibility-profile", help="Prepare a dedicated bottle for a pinned graphics profile")
    profile_setup.add_argument("--profile", required=True, help="Profile id from list-compatibility-profiles")
    profile_setup.add_argument("--dxmt-source", help="Verified DXMT source directory")
    profile_setup.add_argument("--dxvk-source", help="Pinned DXVK-macOS bundle directory")
    profile_setup.add_argument("--moltenvk-source", help="Compatible Sikarugir wrapper or moltenvkcx directory")
    profile_setup.add_argument("--d3dmetal-source", help="D3DMetal directory from the selected GPTK installation")
    profile_setup.add_argument("--winetricks", default="winetricks", help="Path to winetricks")
    profile_setup.add_argument("--interactive", action="store_true", help="Allow interactive Steam installation")
    profile_setup.set_defaults(func=cmd_setup_compatibility_profile)
    profile_reset = sub.add_parser("reset-compatibility-profile", help="Remove one dedicated profile bottle without deleting shared games")
    profile_reset.add_argument("--profile", required=True, help="Profile id from list-compatibility-profiles")
    profile_reset.add_argument("--confirm", action="store_true", help="Confirm removal of the dedicated bottle")
    profile_reset.set_defaults(func=cmd_reset_compatibility_profile)
    attach_library = sub.add_parser("attach-steam-library", help="Attach canonical shared Steam libraries to one managed profile bottle")
    attach_library.add_argument("--all", action="store_true", help="Attach every discovered Steam library")
    attach_library.add_argument("--library-id", action="append", help="Attach one stable library id; may be repeated")
    attach_library.set_defaults(func=cmd_attach_steam_library)
    sub.add_parser("init", help="Create or initialize the Wine prefix").set_defaults(func=cmd_init)
    sub.add_parser("install-steam", help="Download and run SteamSetup.exe").set_defaults(func=cmd_install_steam)

    run_cmd = sub.add_parser("run-steam", help="Launch Steam.exe inside the bottle")
    run_cmd.add_argument("--steam-path", default=steam_windows_path(), help="Windows path to Steam.exe")
    run_cmd.add_argument("--no-wait", action="store_true", help="Return immediately after launching Steam")
    run_cmd.set_defaults(func=cmd_run_steam)

    sub.add_parser("winecfg", help="Open winecfg for the current bottle or prefix").set_defaults(func=cmd_winecfg)

    tricks_cmd = sub.add_parser("winetricks", help="Run winetricks verbs against the bottle")
    tricks_cmd.add_argument("--winetricks", default="winetricks", help="Path to the winetricks executable")
    tricks_cmd.add_argument("--verbs", required=True, help="Comma-separated verbs, for example: vcrun2019,d3dx9")
    tricks_cmd.add_argument("--interactive", action="store_true", help="Run winetricks without -q")
    tricks_cmd.set_defaults(func=cmd_run_winetricks)

    sub.add_parser("kill-wine", help="Stop all Wine processes for the current bottle or prefix").set_defaults(func=cmd_kill_wine)

    sessions_cmd = sub.add_parser("list-sessions", help="Reconcile and list tracked game launch sessions")
    sessions_cmd.add_argument("--all", action="store_true", help="Include exited and failed sessions")
    sessions_cmd.set_defaults(func=cmd_list_sessions)

    stop_game_cmd = sub.add_parser("stop-game", help="Stop one tracked game session without stopping shared Steam")
    stop_game_cmd.add_argument("--session-id", required=True, help="Launch session id returned by a game launch")
    stop_game_cmd.set_defaults(func=cmd_stop_game)

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
    dxmt_cmd.add_argument(
        "--allow-unrecommended-dxmt",
        action="store_true",
        help="Allow DXMT versions outside the validated 0.70/0.71 path, including known-problem versions",
    )
    dxmt_cmd.set_defaults(func=cmd_install_dxmt)

    d3dmetal_cmd = sub.add_parser("install-d3dmetal", help="Install D3DMetal into the bottle from a local folder or tar.gz")
    d3dmetal_cmd.add_argument("--d3dmetal-source", required=True, help="Path to a D3DMetal directory or tar.gz archive")
    d3dmetal_cmd.set_defaults(func=cmd_install_d3dmetal)

    sub.add_parser("list-runtime-catalog", help="List installable Wine and graphics runtimes").set_defaults(
        func=cmd_list_runtime_catalog
    )

    sub.add_parser("list-installed-runtimes", help="List managed runtimes installed by the launcher").set_defaults(
        func=cmd_list_installed_runtimes
    )

    runtime_cmd = sub.add_parser("install-runtime", help="Download, verify, extract, and optionally install a managed runtime")
    runtime_cmd.add_argument("--runtime", required=True, help="Runtime id from list-runtime-catalog")
    runtime_cmd.add_argument(
        "--no-bottle-install",
        action="store_true",
        help="Only download/register the runtime; do not install graphics DLLs into the selected bottle",
    )
    runtime_cmd.set_defaults(func=cmd_install_runtime)

    setup_cmd = sub.add_parser(
        "setup-metal",
        help="Create or reuse a prefix, install Steam via winetricks, install DXMT, and open Steam",
    )
    setup_cmd.add_argument("--dxmt-source", required=True, help="Path to a DXMT directory or tar.gz archive")
    setup_cmd.add_argument(
        "--allow-unrecommended-dxmt",
        action="store_true",
        help="Allow DXMT versions outside the validated 0.70/0.71 path, including known-problem versions",
    )
    setup_cmd.add_argument("--winetricks", default="winetricks", help="Path to the winetricks executable")
    setup_cmd.add_argument("--interactive", action="store_true", help="Run winetricks steam without -q")
    setup_cmd.add_argument("--no-launch", action="store_true", help="Finish setup without opening Steam")
    setup_cmd.add_argument("--no-wait", action="store_true", help="Return immediately after launching Steam")
    setup_cmd.set_defaults(func=cmd_setup_metal)

    wipe_cmd = sub.add_parser("wipe-bottles", help="Delete every bottle under app support")
    wipe_cmd.add_argument("--yes", action="store_true", help="Confirm deletion of all bottles")
    wipe_cmd.set_defaults(func=cmd_wipe_bottles)

    doctor_cmd = sub.add_parser("doctor", help="Check Wine, DXMT, Steam, and manifest health for the target prefix")
    doctor_cmd.add_argument("--winetricks", default="winetricks", help="Path to the winetricks executable")
    doctor_cmd.add_argument("--fix", action="store_true", help="Apply safe fixes, then rerun the checks")
    doctor_cmd.add_argument(
        "--dxmt-source",
        help="Optional DXMT directory or tar.gz archive to reinstall DXMT during --fix",
    )
    doctor_cmd.add_argument(
        "--allow-unrecommended-dxmt",
        action="store_true",
        help="Allow DXMT versions outside the validated 0.70/0.71 path during --fix",
    )
    doctor_cmd.set_defaults(func=cmd_doctor)

    gui_cmd = sub.add_parser("gui", help="Open the simple desktop frontend")
    gui_cmd.add_argument("--no-browser", action="store_true", help="Start the local UI server without opening a browser")
    gui_cmd.set_defaults(func=cmd_gui)

    sub.add_parser("list-games", help="List installed Steam games discovered from manifests").set_defaults(func=cmd_list_games)

    launch_cmd = sub.add_parser("launch-game", help="Launch a Steam game by AppID")
    launch_cmd.add_argument("--appid", required=True, help="Steam AppID")
    launch_cmd.add_argument("--dxmt-source", help="Optional DXMT directory or tar.gz archive to restore DXMT before launch")
    launch_cmd.add_argument("--dxvk-source", help="Optional DXVK directory or tar.gz archive to restore DXVK before launch")
    launch_cmd.add_argument("--dxvk-flavor", choices=("upstream", "macos"), default="upstream")
    launch_cmd.add_argument(
        "--allow-unrecommended-dxmt",
        action="store_true",
        help="Allow DXMT versions outside the validated 0.70/0.71 path before launch",
    )
    launch_cmd.add_argument("--d3dmetal-source", help="Optional D3DMetal directory or tar.gz archive to restore D3DMetal before launch")
    launch_cmd.add_argument("--no-wait", action="store_true", help="Return immediately after sending the launch request")
    launch_cmd.set_defaults(func=cmd_launch_game)

    smart_launch_cmd = sub.add_parser("smart-launch-game", help="Try a direct launch first, then fall back to Steam")
    smart_launch_cmd.add_argument("--appid", required=True, help="Steam AppID")
    smart_launch_cmd.add_argument("--dxmt-source", help="Optional DXMT directory or tar.gz archive to restore DXMT before launch")
    smart_launch_cmd.add_argument(
        "--allow-unrecommended-dxmt",
        action="store_true",
        help="Allow DXMT versions outside the validated 0.70/0.71 path before launch",
    )
    smart_launch_cmd.add_argument("--dxvk-source", help="Optional DXVK directory or tar.gz archive to restore DXVK before launch")
    smart_launch_cmd.add_argument("--dxvk-flavor", choices=("upstream", "macos"), default="upstream")
    smart_launch_cmd.add_argument("--d3dmetal-source", help="Optional D3DMetal directory or tar.gz archive to restore D3DMetal before launch")
    smart_launch_cmd.add_argument("--winetricks", default="winetricks", help="Path to winetricks for first-time hidden D3DMetal setup")
    smart_launch_cmd.add_argument("--probe-seconds", type=int, default=8, help="Seconds to watch the direct launch before considering it healthy")
    smart_launch_cmd.add_argument("--no-wait", action="store_true", help="Return immediately after a healthy launch path is found")
    smart_launch_cmd.set_defaults(func=cmd_smart_launch_game)

    debug_cmd = sub.add_parser("debug-game", help="Launch a game executable directly with Wine debug logging")
    debug_cmd.add_argument("--appid", help="Steam AppID to resolve to an installed game executable")
    debug_cmd.add_argument("--exe", help="Explicit path to a Windows game executable inside the bottle")
    debug_cmd.add_argument("--cwd", help="Optional working directory override")
    debug_cmd.add_argument("--env", action="append", default=[], help="Extra environment override in KEY=VALUE form")
    debug_cmd.add_argument("--dxmt-source", help="Optional DXMT directory or tar.gz archive to restore DXMT before launch")
    debug_cmd.add_argument(
        "--allow-unrecommended-dxmt",
        action="store_true",
        help="Allow DXMT versions outside the validated 0.70/0.71 path before launch",
    )
    debug_cmd.add_argument("--dxvk-source", help="Optional DXVK directory or tar.gz archive to restore DXVK before launch")
    debug_cmd.add_argument("--dxvk-flavor", choices=("upstream", "macos"), default="upstream")
    debug_cmd.add_argument("--d3dmetal-source", help="Optional D3DMetal directory or tar.gz archive to restore D3DMetal before launch")
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

    if is_apple_silicon() and not getattr(args, "json", False) and not getattr(args, "jsonl", False):
        print("[Note] You’re on Apple Silicon. Many Wine/Steam setups run under Rosetta 2.")

    args.func(args)
