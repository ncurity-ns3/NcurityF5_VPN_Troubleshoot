"""Site-specific diagnosis settings (edit resources/config.json as needed)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.paths import resource_path


@dataclass
class AppConfig:
    vpn_fqdn: str = ""
    tunnel_mode: str = "unknown"  # full | split | unknown
    internet_allowed_on_vpn: bool | None = None
    internal_test_hosts: list[str] = field(default_factory=list)
    approved_client_version_prefix: str = "72"
    expected_signer: str = "F5, Inc."


_DEFAULT = AppConfig()


def load_config() -> AppConfig:
    path = resource_path("config.json")
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    return AppConfig(
        vpn_fqdn=str(data.get("vpn_fqdn", "") or ""),
        tunnel_mode=str(data.get("tunnel_mode", "unknown") or "unknown"),
        internet_allowed_on_vpn=data.get("internet_allowed_on_vpn", None),
        internal_test_hosts=list(data.get("internal_test_hosts") or []),
        approved_client_version_prefix=str(
            data.get("approved_client_version_prefix", "72") or "72"
        ),
        expected_signer=str(data.get("expected_signer", "F5, Inc.") or "F5, Inc."),
    )


def ensure_default_config() -> Path:
    path = resource_path("config.json")
    if path.exists():
        return path
    sample = {
        "vpn_fqdn": "",
        "tunnel_mode": "unknown",
        "internet_allowed_on_vpn": None,
        "internal_test_hosts": [],
        "approved_client_version_prefix": "72",
        "expected_signer": "F5, Inc.",
        "_comment": "vpn_fqdn / internal_test_hosts 를 고객사에 맞게 채우면 진단이 정확해집니다.",
    }
    try:
        path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return path
