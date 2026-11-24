"""Resolve VPN FQDN and site settings from user info + config."""

from __future__ import annotations

from app.config import load_config
from app.user_info import get_user_info


def normalize_host(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    for prefix in ("https://", "http://"):
        if v.lower().startswith(prefix):
            v = v[len(prefix) :]
    v = v.split("/")[0].strip()
    # strip port for display host; keep if needed later
    return v


def resolve_vpn_fqdn() -> tuple[str, str]:
    """Return (fqdn, source) where source is 'user_info' | 'config' | ''."""
    info = get_user_info()
    host = normalize_host(info.vpn_domain)
    if host:
        return host, "user_info"
    cfg = load_config()
    host = normalize_host(cfg.vpn_fqdn)
    if host:
        return host, "config"
    return "", ""


def resolve_internal_hosts() -> list[str]:
    return list(load_config().internal_test_hosts or [])
