from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_macos_backend_build_bundles_default_alphasift_adapter() -> None:
    script = (REPO_ROOT / "scripts" / "build-backend-macos.sh").read_text(encoding="utf-8")

    assert "DEFAULT_ALPHASIFT_INSTALL_SPEC" in script
    assert '"${PYTHON_BIN}" -m pip install "${alpha_sift_install_spec}"' in script
    assert "import alphasift.dsa_adapter" in script
    assert '"api.v1.endpoints.alphasift"' in script
    assert '"alphasift"' in script
    assert '"alphasift.dsa_adapter"' in script
    assert "--collect-all alphasift" in script
    assert "packaged AlphaSift adapter files not found" in script
