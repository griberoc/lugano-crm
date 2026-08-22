import base64
import json
from pathlib import Path

from scripts.scan_tracked_secrets import ROOT_DIR, scan_repository, scan_text


def test_repository_has_no_likely_tracked_secrets():
    assert scan_repository(ROOT_DIR) == []


def test_detects_realistic_tokens_without_storing_value_in_finding():
    token = "ghp_" + "a" * 36

    findings = scan_text(Path("config.txt"), f"TOKEN={token}\n")

    assert [(item.line, item.kind) for item in findings] == [(1, "github-token")]
    assert token not in repr(findings[0])


def test_ignores_documented_placeholders_and_empty_values():
    text = "TOKEN=<token-real>\nSUPABASE_SERVICE_ROLE_KEY=\nTOKEN=your-token\n"

    assert scan_text(Path(".env.example"), text) == []


def test_detects_private_key_header():
    findings = scan_text(
        Path("server.pem"),
        "-----BEGIN " + "PRIVATE KEY-----\nredacted\n",
    )

    assert findings[0].kind == "private-key"


def jwt_with_role(role: str) -> str:
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    header = encode(json.dumps({"alg": "HS256"}).encode())
    payload = encode(json.dumps({"role": role, "padding": "x" * 20}).encode())
    return f"{header}.{payload}.{'s' * 24}"


def test_allows_public_supabase_anon_jwt_but_rejects_service_role():
    anon = scan_text(Path("frontend/config.js"), jwt_with_role("anon"))
    service = scan_text(Path("frontend/config.js"), jwt_with_role("service_role"))

    assert anon == []
    assert service[0].kind == "jwt"
