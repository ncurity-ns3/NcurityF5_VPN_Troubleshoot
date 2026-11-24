"""Edge Client install health check (Healthy / Unhealthy + reasons).

Silent — no console windows. Prefer registry/sc over PowerShell.
"""

from __future__ import annotations

import winreg
from dataclasses import dataclass, field
from pathlib import Path

from app.paths import resource_path
from app.winproc import run_silent

F5_VPN_DIR = Path(r"C:\Program Files (x86)\F5 VPN")
F5_VPN_CLIENT = F5_VPN_DIR / "f5fpclientW.exe"
LEGACY_EDGE_DIR = Path(r"C:\Program Files (x86)\F5 Networks\Edge Client")
DOWNLOADED = Path(r"C:\Windows\Downloaded Program Files")
COMPONENT_EXES = [
    DOWNLOADED / "f5vpn.exe",
    DOWNLOADED / "TunnelServer.exe",
]

F5_SERVICES = [
    "F5 Networks Component Installer",
    "F5FltSrv",
    "F5TrafficSrv",
    "F5PrelogonHelperService64",
]
OS_VPN_SERVICES = ["RasMan", "TapiSrv", "SstpSvc"]
VPN_ADAPTER_NAME = "F5 Networks VPN Adapter"


@dataclass
class HealthCheck:
    healthy: bool
    summary: str
    reasons: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _decode(data: bytes | None) -> str:
    if not data:
        return ""
    for enc in ("cp949", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _service_info(name: str) -> tuple[str, str]:
    try:
        r = run_silent(["sc", "query", name], timeout=8)
        text = _decode(r.stdout)
        if r.returncode != 0 and "1060" in text:
            return "MISSING", ""
        if "RUNNING" in text:
            status = "RUNNING"
        elif "STOPPED" in text:
            status = "STOPPED"
        else:
            status = "UNKNOWN"
        start = ""
        r2 = run_silent(["sc", "qc", name], timeout=8)
        qc = _decode(r2.stdout)
        if "AUTO_START" in qc:
            start = "AUTO"
        elif "DEMAND_START" in qc:
            start = "MANUAL"
        elif "DISABLED" in qc:
            start = "DISABLED"
        return status, start
    except Exception:  # noqa: BLE001
        return "ERROR", ""


def _uninstall_entries() -> list[tuple[str, str]]:
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
    ]
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as root:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(root, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(root, sub) as key:
                            name, _ = winreg.QueryValueEx(key, "DisplayName")
                            name_s = str(name)
                            low = name_s.lower()
                            if "edge client" not in low and "big-ip edge" not in low:
                                continue
                            ver = ""
                            try:
                                ver, _ = winreg.QueryValueEx(key, "DisplayVersion")
                            except OSError:
                                pass
                            key_id = name_s.lower()
                            if key_id not in seen:
                                seen.add(key_id)
                                found.append((name_s, str(ver) if ver else ""))
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _vpn_adapter_ok() -> tuple[bool, str]:
    """Find F5 VPN adapter via registry (no PowerShell window)."""
    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(root, sub) as key:
                        try:
                            desc, _ = winreg.QueryValueEx(key, "DriverDesc")
                        except OSError:
                            continue
                        if str(desc) == VPN_ADAPTER_NAME:
                            return True, "OK"
                except OSError:
                    continue
    except OSError as exc:
        return False, f"확인 실패 ({exc})"
    # Fallback: netsh (silent)
    try:
        r = run_silent(["netsh", "interface", "show", "interface"], timeout=10)
        text = _decode(r.stdout)
        if VPN_ADAPTER_NAME in text or "F5 Networks" in text:
            return True, "OK(netsh)"
    except Exception:  # noqa: BLE001
        pass
    return False, "없음"


def check_edge_client_health() -> HealthCheck:
    reasons: list[str] = []
    details: list[str] = []
    soft: list[str] = []
    hard_fail = False

    f5 = resource_path("tools", "f5wininfo.exe")
    details.append(f"f5wininfo: {'사용 가능' if f5.exists() else '없음 (도구 번들)'}")

    entries = _uninstall_entries()
    edge_main = next((e for e in entries if e[0].strip().lower() == "big-ip edge client"), None)
    edge_comp = next((e for e in entries if "components" in e[0].lower()), None)
    for name, ver in entries:
        details.append(f"등록: {name}" + (f" ({ver})" if ver else ""))

    has_main_reg = edge_main is not None
    modern_client = F5_VPN_CLIENT.exists()
    legacy_dir = LEGACY_EDGE_DIR.exists()
    details.append(f"클라이언트: {'있음' if modern_client else '없음'} ({F5_VPN_CLIENT})")
    details.append(
        f"레거시 폴더: {'있음' if legacy_dir else '없음 (최신 설치에서는 정상)'} ({LEGACY_EDGE_DIR})"
    )

    for exe in COMPONENT_EXES:
        ok = exe.exists()
        details.append(f"구성 요소: {'있음' if ok else '없음'} ({exe.name})")
        if not ok:
            hard_fail = True
            reasons.append(f"필수 구성 요소가 없습니다: {exe.name}")

    if not has_main_reg and not modern_client and not legacy_dir:
        hard_fail = True
        reasons.append("BIG-IP Edge Client가 설치되어 있지 않습니다.")
    elif not has_main_reg and modern_client:
        soft.append("클라이언트 파일은 있으나 프로그램 등록(BIG-IP Edge Client)이 없습니다.")
    elif has_main_reg and not modern_client and not legacy_dir:
        hard_fail = True
        reasons.append("등록은 있으나 클라이언트 실행 파일이 없습니다. (손상 가능)")

    if edge_comp is None:
        soft.append("Edge Client Components 등록이 없습니다.")

    for svc in F5_SERVICES:
        status, start = _service_info(svc)
        details.append(f"서비스 {svc}: {status}" + (f" ({start})" if start else ""))
        if status == "MISSING":
            hard_fail = True
            reasons.append(f"F5 서비스가 없습니다: {svc}")
        elif status != "RUNNING" and start == "AUTO":
            hard_fail = True
            reasons.append(f"자동 시작 F5 서비스가 실행 중이 아닙니다: {svc} ({status})")
        elif status != "RUNNING":
            soft.append(f"F5 서비스 중지: {svc} ({status}, {start or '?'})")

    for svc in OS_VPN_SERVICES:
        status, start = _service_info(svc)
        details.append(f"서비스 {svc}: {status}" + (f" ({start})" if start else ""))
        if status == "MISSING":
            hard_fail = True
            reasons.append(f"VPN 관련 서비스가 없습니다: {svc}")
        elif status != "RUNNING":
            soft.append(f"VPN OS 서비스가 중지됨: {svc} ({status}, {start or '?'})")

    adapter_ok, adapter_status = _vpn_adapter_ok()
    details.append(f"VPN 어댑터 ({VPN_ADAPTER_NAME}): {adapter_status}")
    if not adapter_ok:
        hard_fail = True
        reasons.append(f"F5 Networks VPN Adapter가 없거나 비정상입니다. ({adapter_status})")

    try:
        conflicts = list(DOWNLOADED.glob("Conflict.*"))
        if len(conflicts) >= 5:
            soft.append("이전에 설치가 정상적으로 끝나지 않은 흔적이 있습니다.")
            details.append(f"Conflict.* 폴더: {len(conflicts)}개")
    except OSError:
        pass

    if soft:
        details.extend(f"[참고] {s}" for s in soft)

    if hard_fail:
        return HealthCheck(
            healthy=False,
            summary="Unhealthy",
            reasons=reasons or ["알 수 없는 이유로 비정상입니다."],
            details=details,
        )

    ok_reasons = ["Edge Client 설치 및 관련 구성이 정상으로 보입니다."]
    if soft:
        ok_reasons.extend(soft)
    return HealthCheck(
        healthy=True,
        summary="Healthy",
        reasons=ok_reasons,
        details=details,
    )
