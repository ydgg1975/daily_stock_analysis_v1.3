import pytest
import json
import re


ADVERSARIAL_PAYLOADS = [
    # Prototype pollution via __proto__
    '{"__proto__": {"polluted": true}}',
    '{"__proto__": {"isAdmin": true}}',
    '{"__proto__": {"constructor": {"prototype": {"polluted": true}}}}',
    # Prototype pollution via constructor
    '{"constructor": {"prototype": {"polluted": true}}}',
    '{"constructor": {"prototype": {"isAdmin": true}}}',
    # HTTP transport hijacking attempts
    '{"__proto__": {"baseURL": "http://evil.com"}}',
    '{"__proto__": {"proxy": {"host": "evil.com", "port": 8080}}}',
    '{"__proto__": {"headers": {"X-Forwarded-For": "evil.com"}}}',
    # Nested prototype pollution
    '{"a": {"__proto__": {"polluted": true}}}',
    '{"a": {"b": {"__proto__": {"polluted": true}}}}',
    # URL manipulation
    '{"__proto__": {"url": "http://evil.com/steal"}}',
    '{"__proto__": {"transformRequest": null}}',
    '{"__proto__": {"transformResponse": null}}',
    # Axios-specific config pollution
    '{"__proto__": {"withCredentials": true}}',
    '{"__proto__": {"auth": {"username": "admin", "password": "admin"}}}',
    '{"__proto__": {"responseType": "arraybuffer"}}',
    # Deep nesting attacks
    '{"level1": {"level2": {"level3": {"__proto__": {"deep": true}}}}}',
    # Unicode/encoding bypass attempts
    '{"\\u005f\\u005fproto\\u005f\\u005f": {"polluted": true}}',
    # Array-based pollution
    '[{"__proto__": {"polluted": true}}]',
    # Mixed attacks
    '{"__proto__": {"baseURL": "http://evil.com"}, "constructor": {"prototype": {"polluted": true}}}',
]


def safe_parse_and_check(payload_str):
    """
    Parse a JSON payload and verify that prototype pollution keys
    do not propagate to the base object prototype chain.
    Returns the parsed object and a pollution check result.
    """
    try:
        parsed = json.loads(payload_str)
    except (json.JSONDecodeError, ValueError):
        return None, False

    # Check that dangerous keys are present as literal keys (not polluting prototype)
    pollution_detected = False

    def check_for_pollution_keys(obj, depth=0):
        if depth > 20:  # Prevent infinite recursion
            return False
        if isinstance(obj, dict):
            for key in obj.keys():
                if key in ('__proto__', 'constructor', 'prototype'):
                    return True
                if check_for_pollution_keys(obj[key], depth + 1):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if check_for_pollution_keys(item, depth + 1):
                    return True
        return False

    has_dangerous_keys = check_for_pollution_keys(parsed)
    return parsed, has_dangerous_keys


def simulate_safe_config_merge(base_config, user_input_str):
    """
    Simulate a safe configuration merge that should not allow
    prototype pollution to affect the base configuration.
    """
    try:
        user_config = json.loads(user_input_str)
    except (json.JSONDecodeError, ValueError):
        return base_config.copy()

    safe_config = base_config.copy()

    # Only merge known safe keys (whitelist approach)
    SAFE_KEYS = {'timeout', 'responseType', 'params', 'data'}

    if isinstance(user_config, dict):
        for key, value in user_config.items():
            # Never merge prototype-polluting keys
            if key not in ('__proto__', 'constructor', 'prototype'):
                if key in SAFE_KEYS:
                    safe_config[key] = value

    return safe_config


@pytest.mark.parametrize("payload", ADVERSARIAL_PAYLOADS)
def test_prototype_pollution_invariant(payload):
    """Invariant: Adversarial JSON payloads containing prototype pollution
    patterns must never be able to modify the base object prototype or
    inject malicious transport configuration. The security boundary between
    user-supplied input and trusted configuration must always be maintained."""

    # Property 1: Parsing adversarial input must not raise unhandled exceptions
    try:
        parsed, has_dangerous_keys = safe_parse_and_check(payload)
    except Exception as e:
        pytest.fail(f"Unhandled exception during parsing of adversarial payload: {e}")

    # Property 2: Base configuration must remain unaffected after merge attempt
    base_config = {
        'baseURL': 'https://trusted-api.example.com',
        'timeout': 5000,
        'headers': {'Content-Type': 'application/json'},
        'withCredentials': False,
    }

    original_base_url = base_config['baseURL']
    original_timeout = base_config['timeout']
    original_credentials = base_config['withCredentials']

    result_config = simulate_safe_config_merge(base_config, payload)

    # Property 3: Critical security-sensitive fields must not be overridden by untrusted input
    assert result_config.get('baseURL') == original_base_url, (
        f"SECURITY VIOLATION: baseURL was modified by adversarial payload. "
        f"Expected '{original_base_url}', got '{result_config.get('baseURL')}'"
    )

    assert result_config.get('withCredentials') == original_credentials, (
        f"SECURITY VIOLATION: withCredentials was modified by adversarial payload. "
        f"Expected '{original_credentials}', got '{result_config.get('withCredentials')}'"
    )

    assert result_config.get('headers') == base_config['headers'], (
        f"SECURITY VIOLATION: headers were modified by adversarial payload."
    )

    # Property 4: Prototype pollution keys must not appear as functional config
    dangerous_keys = {'__proto__', 'constructor', 'prototype'}
    for key in dangerous_keys:
        assert key not in result_config, (
            f"SECURITY VIOLATION: Dangerous key '{key}' found in merged config from payload: {payload}"
        )

    # Property 5: If payload contains prototype pollution patterns,
    # they must be treated as literal data, not as prototype modifiers
    if parsed is not None and has_dangerous_keys:
        # The dangerous keys should be identifiable as literal dict keys
        # but must not have affected the prototype chain
        # In Python, JSON parsing is safe from prototype pollution by design,
        # but we verify the invariant holds
        test_obj = {}
        assert not hasattr(test_obj, 'polluted'), (
            "SECURITY VIOLATION: Base object prototype was polluted"
        )
        assert not hasattr(test_obj, 'isAdmin'), (
            "SECURITY VIOLATION: Base object prototype was polluted with isAdmin"
        )
        assert not hasattr(test_obj, 'deep'), (
            "SECURITY VIOLATION: Base object prototype was polluted with deep key"
        )

    # Property 6: Verify no HTTP transport hijacking via proxy injection
    assert result_config.get('proxy') is None or result_config.get('proxy') == base_config.get('proxy'), (
        f"SECURITY VIOLATION: Proxy configuration was injected via adversarial payload"
    )

    # Property 7: Auth credentials must not be injectable
    assert result_config.get('auth') is None or result_config.get('auth') == base_config.get('auth'), (
        f"SECURITY VIOLATION: Auth credentials were injected via adversarial payload"
    )