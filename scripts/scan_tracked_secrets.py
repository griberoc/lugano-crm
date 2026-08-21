"""Detect likely real secrets in Git-tracked text files without printing values."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

PLACEHOLDER_MARKERS = (
    "<",
    "change-me",
    "change-this",
    "example",
    "placeholder",
    "sua-",
    "seu-",
    "your-",
)

TOKEN_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "jwt": re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
    ),
    "github-token": re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{30,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "mercado-pago-token": re.compile(r"\bAPP_USR-[A-Za-z0-9_-]{20,}\b"),
    "supabase-secret-key": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{20,}\b"),
}


def is_public_supabase_anon_jwt(token: str) -> bool:
    try:
        payload = token.split(".", 2)[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (IndexError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return claims.get("role") == "anon"


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    kind: str


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def is_placeholder(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if is_placeholder(line):
            continue
        for kind, pattern in TOKEN_PATTERNS.items():
            match = pattern.search(line)
            if match and kind == "jwt" and is_public_supabase_anon_jwt(match.group(0)):
                continue
            if match:
                findings.append(Finding(path=path, line=line_number, kind=kind))
    return findings


def scan_repository(root: Path = ROOT_DIR) -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_files(root):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="ignore")
        findings.extend(scan_text(path.relative_to(root), text))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Busca possiveis segredos reais em arquivos rastreados pelo Git.",
    )
    parser.add_argument("--root", type=Path, default=ROOT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings = scan_repository(args.root.resolve())
    for finding in findings:
        # Deliberadamente nao imprime o trecho ou o valor encontrado.
        print(f"[FAIL] {finding.path}:{finding.line}: {finding.kind}")
    if findings:
        print(f"Falha: {len(findings)} possivel(is) segredo(s) rastreado(s).")
        return 1
    print("OK: nenhum padrao de segredo real encontrado em arquivos rastreados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
