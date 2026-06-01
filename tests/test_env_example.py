from pathlib import Path

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def _read_env_example() -> str:
    return ENV_EXAMPLE.read_text(encoding="utf-8")


def test_env_example_file_exists():
    assert ENV_EXAMPLE.is_file()


def test_xfyun_channel_is_documented():
    content = _read_env_example()
    assert "讯飞星辰" in content
    assert "XFYUN_API_KEY" in content
    assert "XFYUN_BASE_URL" in content


def test_xfyun_uses_anthropic_protocol():
    content = _read_env_example()
    assert "Anthropic 协议" in content


def test_xfyun_entries_are_commented_out():
    for line in _read_env_example().splitlines():
        if "XFYUN_" in line:
            assert line.lstrip().startswith("#")
