from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PyInstallerCommand:
    name: str
    args: list[str]


@dataclass(frozen=True)
class SidecarBuildPlan:
    root: Path
    output_dir: Path
    pyinstaller_config_dir: Path
    commands: list[PyInstallerCommand]
    expected_binaries: list[Path]


@dataclass(frozen=True)
class SidecarSpec:
    name: str
    entrypoint: Path
    source_path: Path
    hidden_imports: tuple[str, ...] = ()
    data_paths: tuple[tuple[Path, str], ...] = ()


SIDECARS = (
    SidecarSpec(
        name="minixd",
        entrypoint=Path("daemon/src/minixd/__main__.py"),
        source_path=Path("daemon/src"),
        hidden_imports=(
            "uvicorn.logging",
            "uvicorn.loops.auto",
            "uvicorn.protocols.http.auto",
            "uvicorn.protocols.websockets.auto",
            "uvicorn.lifespan.on",
        ),
        data_paths=((Path("profiles"), "profiles"),),
    ),
    SidecarSpec(
        name="minix-mcp",
        entrypoint=Path("mcp/src/minix_mcp/__main__.py"),
        source_path=Path("mcp/src"),
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build MiniX Print Studio Python sidecar binaries with PyInstaller."
    )
    parser.add_argument(
        "--python",
        default=None,
        help="Python executable that can run PyInstaller.",
    )
    parser.add_argument(
        "--target-platform",
        default=sys.platform,
        help="Target platform for sidecar binaries. PyInstaller does not cross-compile.",
    )
    args = parser.parse_args(argv)

    root = Path.cwd()
    if args.target_platform != sys.platform:
        parser.error(
            f"cannot build {args.target_platform} sidecars on {sys.platform}; "
            "run this command on the target OS"
        )
    python_executable = args.python or default_python_executable(root, platform=sys.platform)
    plan = build_sidecar_plan(
        root=root,
        python_executable=python_executable,
        platform=args.target_platform,
    )
    run_sidecar_plan(plan)
    print(f"sidecar build passed: {plan.output_dir}")
    return 0


def build_sidecar_plan(
    *,
    root: Path,
    python_executable: str,
    platform: str,
) -> SidecarBuildPlan:
    output_dir = root / "dist" / "sidecars"
    build_root = root / "build" / "pyinstaller"
    spec_dir = build_root / "specs"
    pyinstaller_config_dir = build_root / "config"
    executable_suffix = ".exe" if platform == "win32" else ""
    commands: list[PyInstallerCommand] = []
    expected_binaries: list[Path] = []

    for sidecar in SIDECARS:
        commands.append(
            PyInstallerCommand(
                name=sidecar.name,
                args=[
                    python_executable,
                    "-m",
                    "PyInstaller",
                    "--noconfirm",
                    "--clean",
                    "--onefile",
                    "--distpath",
                    str(output_dir),
                    "--workpath",
                    str(build_root / sidecar.name),
                    "--specpath",
                    str(spec_dir),
                    "--paths",
                    str(root / sidecar.source_path),
                    *hidden_import_args(sidecar.hidden_imports),
                    *add_data_args(sidecar.data_paths, root=root, platform=platform),
                    "--name",
                    sidecar.name,
                    str(root / sidecar.entrypoint),
                ],
            )
        )
        expected_binaries.append(output_dir / f"{sidecar.name}{executable_suffix}")

    return SidecarBuildPlan(
        root=root,
        output_dir=output_dir,
        pyinstaller_config_dir=pyinstaller_config_dir,
        commands=commands,
        expected_binaries=expected_binaries,
    )


def default_python_executable(root: Path, platform: str) -> str:
    venv_python = (
        root / ".venv" / "Scripts" / "python.exe"
        if platform == "win32"
        else root / ".venv" / "bin" / "python"
    )
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def run_sidecar_plan(plan: SidecarBuildPlan) -> None:
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    plan.pyinstaller_config_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "PYINSTALLER_CONFIG_DIR": str(plan.pyinstaller_config_dir),
    }
    for command in plan.commands:
        subprocess.run(command.args, cwd=plan.root, check=True, env=env)

    missing = [path for path in plan.expected_binaries if not path.is_file()]
    if missing:
        missing_list = ", ".join(path.as_posix() for path in missing)
        raise RuntimeError(f"missing expected sidecar binaries: {missing_list}")


def hidden_import_args(hidden_imports: tuple[str, ...]) -> list[str]:
    args: list[str] = []
    for hidden_import in hidden_imports:
        args.extend(["--hidden-import", hidden_import])
    return args


def add_data_args(
    data_paths: tuple[tuple[Path, str], ...],
    *,
    root: Path,
    platform: str,
) -> list[str]:
    separator = ";" if platform == "win32" else ":"
    args: list[str] = []
    for source, destination in data_paths:
        args.extend(["--add-data", f"{root / source}{separator}{destination}"])
    return args


if __name__ == "__main__":
    raise SystemExit(main())
