import importlib
import importlib.util


def test_mcp_server_is_importable_package():
    module = importlib.import_module("mcp_server")
    assert hasattr(module, "__path__"), "mcp_server should be an importable package"


def test_mcp_server_server_module_is_discoverable():
    spec = importlib.util.find_spec("mcp_server.server")
    assert spec is not None, "mcp_server.server should be discoverable for `python -m mcp_server.server`"
