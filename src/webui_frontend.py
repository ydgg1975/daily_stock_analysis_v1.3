# -*- coding: utf-8 -*-
"""
WebUI frontend asset preparation helper.

Default behavior runs startup-time frontend auto build.
Set WEBUI_AUTO_BUILD=false to disable auto build and only verify artifacts.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

_FALSEY_ENV_VALUES = {"0", "false", "no", "off"}
_BUILD_INPUT_FILES = (
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "eslint.config.js",
    "postcss.config.js",
    "tailwind.config.js",
    "index.html",
)
_BUILD_INPUT_DIRS = ("src", "public")


def _is_truthy_env(var_name: str, default: str = "true") -> bool:
    """환경 변수 값을 일반적인 true/false 규칙으로 해석합니다."""
    value = os.getenv(var_name, default).strip().lower()
    return value not in _FALSEY_ENV_VALUES


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _tree_latest_mtime(root: Path) -> float:
    if not root.exists():
        return 0.0
    latest = 0.0
    try:
        for p in root.rglob("*"):
            if p.is_file():
                latest = max(latest, _safe_mtime(p))
    except OSError:
        latest = max(latest, _safe_mtime(root))
    return latest


def _max_mtime(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        latest = max(latest, _safe_mtime(path))
    return latest


def _resolve_artifact_index(frontend_dir: Path) -> Path:
    # 이 저장소의 기본 WebUI 산출물 위치는 static/index.html입니다.
    static_index = (frontend_dir / ".." / ".." / "static" / "index.html").resolve()
    dist_index = frontend_dir / "dist" / "index.html"
    build_index = frontend_dir / "build" / "index.html"
    if static_index.exists():
        return static_index

    fallback_candidates = [p for p in (dist_index, build_index) if p.exists()]
    if not fallback_candidates:
        return static_index
    return max(fallback_candidates, key=_safe_mtime)


def _needs_dependency_install(frontend_dir: Path, package_json: Path, lock_file: Path, force_build: bool) -> bool:
    node_modules_dir = frontend_dir / "node_modules"
    install_marker = node_modules_dir / ".package-lock.json"
    deps_marker_mtime = _safe_mtime(install_marker) if install_marker.exists() else _safe_mtime(node_modules_dir)
    deps_input_mtime = _max_mtime((package_json, lock_file))
    return force_build or (not node_modules_dir.exists()) or (deps_marker_mtime < deps_input_mtime)


def _collect_build_inputs_latest_mtime(frontend_dir: Path) -> float:
    latest = _max_mtime(frontend_dir / filename for filename in _BUILD_INPUT_FILES)
    for dirname in _BUILD_INPUT_DIRS:
        latest = max(latest, _tree_latest_mtime(frontend_dir / dirname))
    return latest


def _needs_frontend_build(frontend_dir: Path, force_build: bool) -> tuple[bool, Path]:
    artifact_index = _resolve_artifact_index(frontend_dir)
    inputs_latest_mtime = _collect_build_inputs_latest_mtime(frontend_dir)
    artifact_mtime = _safe_mtime(artifact_index)
    needs_build = force_build or (not artifact_index.exists()) or (artifact_mtime < inputs_latest_mtime)
    return needs_build, artifact_index


def _run_frontend_commands(commands: Sequence[Sequence[str]], frontend_dir: Path) -> bool:
    try:
        for command in commands:
            logger.info("프런트엔드 명령 실행: %s", " ".join(command))
            subprocess.run(command, cwd=frontend_dir, check=True)
        logger.info("프런트엔드 산출물 준비가 완료되었습니다")
        return True
    except subprocess.CalledProcessError as exc:
        cmd_display = " ".join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
        logger.error(
            "프런트엔드 명령 실행 실패(exit_code=%s): %s",
            getattr(exc, "returncode", "N/A"),
            cmd_display,
        )
        return False


def _manual_build_command(frontend_dir: Path) -> str:
    lock_file = frontend_dir / "package-lock.json"
    install_cmd = "npm ci" if lock_file.exists() else "npm install"
    return f'cd "{frontend_dir}" && {install_cmd} && npm run build'


def _has_static_assets(static_dir: Path) -> bool:
    """static/assets/ 안에 CSS 또는 JS 산출물이 있는지 확인합니다."""
    assets_dir = static_dir / "assets"
    if not assets_dir.is_dir():
        return False
    try:
        return any(
            f.suffix in (".js", ".css") and f.is_file()
            for f in assets_dir.iterdir()
        )
    except OSError:
        return False


def _warn_if_assets_missing(artifact_index: Path, frontend_dir: Path) -> None:
    """index.html만 있고 assets 산출물이 없으면 WebUI 표시 오류를 경고합니다."""
    static_dir = artifact_index.parent
    assets_dir = static_dir / "assets"
    if not _has_static_assets(static_dir):
        logger.warning(
            "감지된 WebUI 산출물 %s에 필요한 %s CSS/JS 파일이 없습니다. "
            "WebUI가 스타일이나 스크립트 없이 비정상 표시될 수 있습니다.",
            artifact_index,
            assets_dir,
        )
        logger.warning("수동 빌드 명령: %s", _manual_build_command(frontend_dir))
        logger.warning(
            "Docker 배포에서는 docker-compose -f ./docker/docker-compose.yml build --no-cache 명령으로 이미지를 다시 빌드하세요."
        )


def prepare_webui_frontend_assets() -> bool:
    """
    WebUI 시작 전에 프런트엔드 산출물을 준비합니다.

    기본 모드(WEBUI_AUTO_BUILD=true):
    - 의존성이나 소스가 바뀌었거나 산출물이 없으면 npm install/build를 실행합니다.

    수동 모드(WEBUI_AUTO_BUILD=false):
    - 백엔드 시작 중 프런트엔드를 컴파일하지 않습니다.
    - 기존 산출물 사용 가능 여부만 확인합니다.
    """
    frontend_dir = Path(__file__).resolve().parent.parent / "apps" / "dsa-web"
    auto_build_enabled = _is_truthy_env("WEBUI_AUTO_BUILD", "true")
    artifact_index = _resolve_artifact_index(frontend_dir)

    if not auto_build_enabled:
        if artifact_index.exists():
            logger.info("WEBUI_AUTO_BUILD=false이며 기존 프런트엔드 산출물을 사용합니다: %s", artifact_index)
            _warn_if_assets_missing(artifact_index, frontend_dir)
            return True
        logger.warning("기존 WebUI 산출물을 찾을 수 없습니다: %s", artifact_index)
        logger.warning("현재 WEBUI_AUTO_BUILD=false라서 자동 빌드를 실행하지 않습니다.")
        logger.warning("수동 프런트엔드 빌드 명령: %s", _manual_build_command(frontend_dir))
        logger.warning("자동 빌드를 원하면 WEBUI_AUTO_BUILD=true로 설정하세요.")
        return False

    force_build = _is_truthy_env("WEBUI_FORCE_BUILD", "false")
    needs_build, artifact_index = _needs_frontend_build(frontend_dir=frontend_dir, force_build=force_build)

    if not needs_build:
        logger.info("재사용 가능한 프런트엔드 산출물을 감지했습니다: %s", artifact_index)
        _warn_if_assets_missing(artifact_index, frontend_dir)
        return True

    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        logger.warning("프런트엔드 프로젝트를 찾을 수 없어 자동 빌드할 수 없습니다: %s", package_json)
        logger.warning("기존 산출물이 없으면 WEBUI_AUTO_BUILD 설정을 확인하세요.")
        return False

    npm_path = shutil.which("npm")
    if not npm_path:
        logger.warning("npm을 찾을 수 없어 프런트엔드를 자동 빌드할 수 없습니다.")
        logger.warning("수동 프런트엔드 빌드 명령: %s", _manual_build_command(frontend_dir))
        return False

    lock_file = frontend_dir / "package-lock.json"
    needs_install = _needs_dependency_install(
        frontend_dir=frontend_dir,
        package_json=package_json,
        lock_file=lock_file,
        force_build=force_build,
    )

    commands = []
    if needs_install:
        lock_exists = (frontend_dir / "package-lock.json").exists()
        commands.append([npm_path, "ci" if lock_exists else "install"])
    if needs_build:
        commands.append([npm_path, "run", "build"])

    logger.info(
        "프런트엔드 준비 상태: needs_install=%s, needs_build=%s, artifact=%s",
        needs_install,
        needs_build,
        artifact_index,
    )
    return _run_frontend_commands(commands=commands, frontend_dir=frontend_dir)
