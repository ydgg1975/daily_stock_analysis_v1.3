import logging

import src.webui_frontend as webui_frontend


def _prepare_fake_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    module_path = repo_root / "src" / "webui_frontend.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    monkeypatch.setattr(webui_frontend, "__file__", str(module_path))
    return repo_root


def _create_full_static(repo_root):
    """Create static/index.html + static/assets/*.js/.css (complete build)."""
    static_dir = repo_root / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (assets_dir / "index-abc123.js").write_text("/* js */", encoding="utf-8")
    (assets_dir / "index-abc123.css").write_text("/* css */", encoding="utf-8")
    return static_dir


def test_prepare_webui_frontend_assets_reuses_prebuilt_static_without_source(tmp_path, monkeypatch, caplog):
    repo_root = _prepare_fake_repo(tmp_path, monkeypatch)
    _create_full_static(repo_root)

    monkeypatch.delenv("WEBUI_AUTO_BUILD", raising=False)
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)
    monkeypatch.setattr(webui_frontend.shutil, "which", lambda _: None)

    with caplog.at_level(logging.INFO):
        assert webui_frontend.prepare_webui_frontend_assets() is True

    assert "재사용 가능한 프런트엔드 산출물을 감지했습니다" in caplog.text
    assert "프런트엔드 프로젝트를 찾을 수 없어 자동 빌드할 수 없습니다" not in caplog.text
    assert "npm을 찾을 수 없어 프런트엔드를 자동 빌드할 수 없습니다" not in caplog.text
    assert "CSS/JS 파일이 없습니다" not in caplog.text


def test_prepare_webui_frontend_assets_fails_without_static_or_source(tmp_path, monkeypatch, caplog):
    _prepare_fake_repo(tmp_path, monkeypatch)

    monkeypatch.delenv("WEBUI_AUTO_BUILD", raising=False)
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)

    with caplog.at_level(logging.WARNING):
        assert webui_frontend.prepare_webui_frontend_assets() is False

    assert "프런트엔드 프로젝트를 찾을 수 없어 자동 빌드할 수 없습니다" in caplog.text


def test_prepare_webui_frontend_assets_warns_when_assets_missing(tmp_path, monkeypatch, caplog):
    """index.html은 있지만 static/assets/가 없으면 WebUI 표시 오류를 경고합니다."""
    repo_root = _prepare_fake_repo(tmp_path, monkeypatch)
    static_index = repo_root / "static" / "index.html"
    static_index.parent.mkdir(parents=True)
    static_index.write_text("<!doctype html>", encoding="utf-8")

    monkeypatch.delenv("WEBUI_AUTO_BUILD", raising=False)
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)
    monkeypatch.setattr(webui_frontend.shutil, "which", lambda _: None)

    with caplog.at_level(logging.WARNING):
        result = webui_frontend.prepare_webui_frontend_assets()

    assert result is True
    assert "CSS/JS 파일이 없습니다" in caplog.text
    assert "WebUI가 스타일이나 스크립트 없이 비정상 표시될 수 있습니다" in caplog.text


def test_prepare_webui_frontend_assets_auto_build_disabled_warns_when_assets_missing(tmp_path, monkeypatch, caplog):
    """WEBUI_AUTO_BUILD=false이고 assets가 없을 때도 경고합니다."""
    repo_root = _prepare_fake_repo(tmp_path, monkeypatch)
    static_index = repo_root / "static" / "index.html"
    static_index.parent.mkdir(parents=True)
    static_index.write_text("<!doctype html>", encoding="utf-8")

    monkeypatch.setenv("WEBUI_AUTO_BUILD", "false")
    monkeypatch.delenv("WEBUI_FORCE_BUILD", raising=False)

    with caplog.at_level(logging.WARNING):
        result = webui_frontend.prepare_webui_frontend_assets()

    assert result is True
    assert "CSS/JS 파일이 없습니다" in caplog.text


def test_has_static_assets_returns_false_for_missing_dir(tmp_path):
    assert webui_frontend._has_static_assets(tmp_path / "nonexistent") is False


def test_has_static_assets_returns_false_for_empty_assets(tmp_path):
    (tmp_path / "assets").mkdir()
    assert webui_frontend._has_static_assets(tmp_path) is False


def test_has_static_assets_returns_true_when_js_present(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("", encoding="utf-8")
    assert webui_frontend._has_static_assets(tmp_path) is True


def test_has_static_assets_returns_true_when_css_present(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "style.css").write_text("", encoding="utf-8")
    assert webui_frontend._has_static_assets(tmp_path) is True
