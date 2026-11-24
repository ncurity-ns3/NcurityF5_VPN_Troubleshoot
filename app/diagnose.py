"""Shared diagnosis engines + user-facing reports.

Disposition:
  ok            — 정상
  pc_issue      — PC에서 원인 확인, 복구 안내 가능
  suspect       — PC에서 이상 징후, 추가 확인 필요
  needs_admin   — BIG-IP/인증/정책 등 관리자 확인 필요
  skip          — 설정·권한·연결 상태 때문에 검사 불가 (실패로 치지 않음)
"""

from __future__ import annotations

import ctypes
import socket
import ssl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from app.config import load_config
from app.health import (
    COMPONENT_EXES,
    F5_SERVICES,
    F5_VPN_CLIENT,
    OS_VPN_SERVICES,
    VPN_ADAPTER_NAME,
    _service_info,
    _uninstall_entries,
    _vpn_adapter_ok,
)
from app.paths import resource_path, troubleshoot_dir
from app.winproc import run_silent

LogFn = Callable[[str], None]

# ok | pc_issue | suspect | needs_admin | skip
Disposition = str


@dataclass
class CheckResult:
    id: str
    user_label: str
    status: Disposition
    user_detail: str
    tech_detail: str = ""
    fix_hint: str = ""
    # Safe user fix action id — see remediations in main_window / actions
    # install_sectigo | restart_client | launch_installer | none
    fix_action: str = ""
    # blocks dependent checks when True (e.g. DNS fail → skip HTTPS)
    blocks_followup: bool = False


@dataclass
class DiagnosisReport:
    symptom_id: str
    symptom_title: str
    results: list[CheckResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def _of(self, *statuses: str) -> list[CheckResult]:
        return [r for r in self.results if r.status in statuses]

    @property
    def has_pc_issue(self) -> bool:
        return bool(self._of("pc_issue"))

    @property
    def has_suspect(self) -> bool:
        return bool(self._of("suspect"))

    @property
    def has_needs_admin(self) -> bool:
        return bool(self._of("needs_admin"))

    def headline(self) -> str:
        if self.has_pc_issue:
            return "PC에서 확인할 수 있는 문제가 있습니다"
        if self.has_needs_admin:
            return "관리자 확인이 필요합니다"
        if self.has_suspect:
            return "추가 확인이 필요한 항목이 있습니다"
        if any(r.status == "skip" for r in self.results) and all(
            r.status in ("ok", "skip") for r in self.results
        ):
            return "일부 항목은 검사할 수 없었습니다"
        return "특별한 문제가 발견되지 않았습니다"

    def summary(self) -> str:
        for st in ("pc_issue", "needs_admin", "suspect"):
            items = self._of(st)
            if items:
                return items[0].user_detail
        skips = self._of("skip")
        if skips and not self._of("pc_issue", "needs_admin", "suspect"):
            return "설정이 없어 일부 점검을 건너뛰었습니다. 결과는 저장해 관리자에게 전달할 수 있습니다."
        return "지금은 큰 장애 신호가 보이지 않습니다. 문제가 계속되면 결과를 저장해 관리자에게 문의해 주세요."

    def recommended_fix(self) -> str:
        for r in self._of("pc_issue"):
            if r.fix_hint:
                return r.fix_hint
        for r in self._of("needs_admin"):
            if r.fix_hint:
                return r.fix_hint
        for r in self._of("suspect"):
            if r.fix_hint:
                return r.fix_hint
        return "진단 결과를 저장한 뒤 관리자에게 전달해 주세요. 임의로 네트워크 초기화나 재설치는 하지 마세요."


def _decode(data: bytes | None) -> str:
    if not data:
        return ""
    for enc in ("cp949", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _run(cmd: list[str], timeout: int = 12) -> tuple[int, str]:
    try:
        r = run_silent(cmd, timeout=timeout)
        return r.returncode, _decode(r.stdout) + _decode(r.stderr)
    except Exception as exc:  # noqa: BLE001
        return -1, str(exc)


# ----- engines -----

def check_install_presence(_log: LogFn | None = None) -> CheckResult:
    entries = _uninstall_entries()
    modern = F5_VPN_CLIENT.exists()
    tech = f"reg={len(entries)}, client={modern}"
    if modern or any("big-ip edge client" == e[0].lower() for e in entries):
        ver = next((e[1] for e in entries if e[0].lower() == "big-ip edge client"), "")
        return CheckResult(
            "install_presence",
            "VPN 프로그램 설치",
            "ok",
            f"VPN 프로그램이 설치되어 있습니다{f' (버전 {ver})' if ver else ''}.",
            tech,
        )
    return CheckResult(
        "install_presence",
        "VPN 프로그램 설치",
        "pc_issue",
        "VPN 프로그램이 설치되어 있지 않거나 손상된 것 같습니다.",
        tech,
        "아래 「설치 파일 실행」으로 재설치를 시도할 수 있습니다.",
        fix_action="launch_installer",
    )


def check_component_files(_log: LogFn | None = None) -> CheckResult:
    missing = [p.name for p in COMPONENT_EXES if not p.exists()]
    tech = f"missing={missing}"
    if not missing:
        return CheckResult(
            "component_files",
            "필수 구성 요소",
            "ok",
            "필수 구성 요소 파일이 있습니다.",
            tech,
        )
    return CheckResult(
        "component_files",
        "필수 구성 요소",
        "pc_issue",
        "VPN에 필요한 구성 요소 일부가 없습니다.",
        tech,
        "관리자에게 VPN 프로그램 재설치를 요청해 주세요.",
    )


def check_client_binary(_log: LogFn | None = None) -> CheckResult:
    if F5_VPN_CLIENT.exists():
        return CheckResult(
            "client_binary",
            "실행 파일",
            "ok",
            "VPN 프로그램 실행 파일이 있습니다.",
            str(F5_VPN_CLIENT),
            "실행이 안 되면 프로그램을 종료 후 다시 열어 보세요.",
        )
    return CheckResult(
        "client_binary",
        "실행 파일",
        "pc_issue",
        "VPN 프로그램 실행 파일을 찾을 수 없습니다.",
        str(F5_VPN_CLIENT),
        "관리자에게 재설치를 요청해 주세요.",
    )


def check_installer_signature(_log: LogFn | None = None) -> CheckResult:
    folder = resource_path("installers")
    cands = sorted(folder.glob("BIGIPEdgeClient*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        return CheckResult(
            "installer_signature",
            "설치 파일 서명",
            "skip",
            "번들된 설치 파일이 없어 서명 검사를 건너뛰었습니다.",
            "no installer in resources/installers",
        )
    path = cands[0]
    cfg = load_config()
    # Prefer signtool-free check via PowerShell, always hidden (no console flash).
    from app.winproc import run_powershell_silent

    ps = (
        f"$s = Get-AuthenticodeSignature -FilePath '{path}'; "
        "Write-Output ($s.Status.ToString() + '|' + [string]$s.SignerCertificate.Subject + '|' + [string]$s.StatusMessage)"
    )
    try:
        r = run_powershell_silent(ps, timeout=25)
        code, out = r.returncode, _decode(r.stdout) + _decode(r.stderr)
    except Exception as exc:  # noqa: BLE001
        code, out = -1, str(exc)
    line = out.strip().splitlines()[-1] if out.strip() else ""
    parts = line.split("|")
    status_part = parts[0] if parts else ""
    subject = parts[1] if len(parts) > 1 else ""
    msg = parts[2] if len(parts) > 2 else ""
    tech = f"{path.name}: status={status_part} subject={subject} msg={msg} exit={code}"
    signer_ok = (not cfg.expected_signer) or (cfg.expected_signer.lower() in subject.lower()) or (
        "f5" in subject.lower()
    )
    if status_part == "Valid" and signer_ok:
        return CheckResult(
            "installer_signature",
            "설치 파일 서명",
            "ok",
            "설치 파일 디지털 서명이 유효합니다.",
            tech,
        )
    if status_part == "Valid":
        return CheckResult(
            "installer_signature",
            "설치 파일 서명",
            "suspect",
            "서명은 유효하지만 예상 게시자와 다를 수 있습니다.",
            tech,
            "관리자에게 승인된 설치 파일인지 확인해 주세요.",
        )
    # Often UnknownError / NotTrusted when root is only in CurrentUser — cert fix first
    if status_part in ("UnknownError", "NotTrusted", "HashMismatch") or "trust" in msg.lower():
        return CheckResult(
            "installer_signature",
            "설치 파일 서명",
            "pc_issue",
            "설치 파일 서명을 아직 신뢰하지 못했습니다. 코드 서명 인증서 문제일 수 있습니다.",
            tech,
            "먼저 「인증서 설치」를 실행한 뒤 다시 점검해 주세요.",
            fix_action="install_sectigo",
        )
    return CheckResult(
        "installer_signature",
        "설치 파일 서명",
        "needs_admin",
        "설치 파일 서명을 확인할 수 없습니다. 관리자에게 문의해 주세요.",
        tech,
        "진단 결과를 저장해 관리자에게 전달해 주세요.",
    )


def _cert_cn_present(cn: str, store: str, user: bool) -> bool:
    """Detect cert by CN via certutil only (no PowerShell window)."""
    cmd = ["certutil", "-user", "-store", store] if user else ["certutil", "-store", store]
    try:
        r = run_silent(cmd, timeout=25)
        return cn in _decode(r.stdout)
    except Exception:  # noqa: BLE001
        return False


def check_cert_sectigo_chain(_log: LogFn | None = None) -> CheckResult:
    """Check Machine + CurrentUser Root/CA (same places certmgr shows)."""
    root_name = "Sectigo Public Code Signing Root R46"
    ca_name = "Sectigo Public Code Signing CA EV R36"
    root_m = _cert_cn_present(root_name, "Root", user=False)
    root_u = _cert_cn_present(root_name, "Root", user=True)
    ca_m = _cert_cn_present(ca_name, "CA", user=False)
    ca_u = _cert_cn_present(ca_name, "CA", user=True)
    root_ok = root_m or root_u
    ca_ok = ca_m or ca_u
    tech = f"root_machine={root_m}, root_user={root_u}, ca_machine={ca_m}, ca_user={ca_u}"
    if root_ok and ca_ok:
        return CheckResult(
            "cert_sectigo_chain",
            "코드 서명 인증서",
            "ok",
            "필요한 코드 서명 인증서가 설치되어 있습니다.",
            tech,
        )
    missing = []
    if not root_ok:
        missing.append("루트 인증서")
    if not ca_ok:
        missing.append("중간 인증서")
    return CheckResult(
        "cert_sectigo_chain",
        "코드 서명 인증서",
        "pc_issue",
        f"필요한 코드 서명 인증서({', '.join(missing)})가 없습니다.",
        tech,
        "「인증서 설치」를 실행한 뒤 다시 점검해 주세요.",
        fix_action="install_sectigo",
    )


def check_windows_installer(_log: LogFn | None = None) -> CheckResult:
    code, out = _run(["sc", "query", "msiserver"], timeout=8)
    if "RUNNING" in out or "STOPPED" in out:
        return CheckResult(
            "windows_installer",
            "Windows 설치 기능",
            "ok",
            "Windows 설치 기능은 사용 가능한 상태입니다.",
            out.splitlines()[0] if out else f"code={code}",
        )
    return CheckResult(
        "windows_installer",
        "Windows 설치 기능",
        "suspect",
        "Windows 설치 기능 상태를 확인하지 못했습니다.",
        out,
        "PC를 다시 시작한 뒤 설치를 재시도해 보세요.",
    )


def check_leftover_install(_log: LogFn | None = None) -> CheckResult:
    n = 0
    try:
        n = len(list(Path(r"C:\Windows\Downloaded Program Files").glob("Conflict.*")))
    except OSError:
        pass
    if n >= 10:
        return CheckResult(
            "leftover_install",
            "이전 설치 흔적",
            "suspect",
            "이전에 설치가 제대로 끝나지 않은 흔적이 있을 수 있습니다.",
            f"Conflict.*={n}",
            "설치가 계속 실패하면 관리자에게 이전 설치 정리를 요청해 주세요.",
        )
    return CheckResult(
        "leftover_install",
        "이전 설치 흔적",
        "ok",
        "이전 설치와 관련된 이상 흔적은 없습니다.",
        f"Conflict.*={n}",
    )


def check_admin_elevation(_log: LogFn | None = None) -> CheckResult:
    try:
        elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        elevated = False
    if elevated:
        return CheckResult(
            "admin_elevation",
            "관리자 권한",
            "ok",
            "관리자 권한으로 실행 중입니다.",
            "elevated=True",
        )
    return CheckResult(
        "admin_elevation",
        "관리자 권한",
        "pc_issue",
        "관리자 권한이 없어 설치·복구가 막힐 수 있습니다.",
        "elevated=False",
        "프로그램을 마우스 오른쪽 버튼 → 관리자 권한으로 실행해 주세요.",
    )


def check_f5_services(_log: LogFn | None = None) -> CheckResult:
    bad_auto: list[str] = []
    soft: list[str] = []
    details: list[str] = []
    for name in F5_SERVICES:
        status, start = _service_info(name)
        details.append(f"{name}={status}/{start}")
        if status == "MISSING":
            bad_auto.append(name)
        elif status != "RUNNING" and start == "AUTO":
            bad_auto.append(name)
        elif status != "RUNNING":
            soft.append(name)
    tech = "; ".join(details)
    if bad_auto:
        return CheckResult(
            "f5_services",
            "VPN 관련 서비스",
            "pc_issue",
            "VPN에 필요한 서비스가 없거나 자동 시작 서비스가 중지되어 있습니다.",
            tech,
            "VPN 프로그램을 다시 실행해 보세요. 계속되면 관리자에게 문의하세요.",
            fix_action="restart_client",
        )
    if soft:
        return CheckResult(
            "f5_services",
            "VPN 관련 서비스",
            "suspect",
            "일부 VPN 서비스가 중지되어 있습니다. 항상 오류는 아닐 수 있습니다.",
            tech,
            "실행이 안 되면 프로그램을 다시 실행해 보세요.",
        )
    return CheckResult(
        "f5_services",
        "VPN 관련 서비스",
        "ok",
        "VPN 관련 서비스 상태가 양호합니다.",
        tech,
    )


def check_os_vpn_services(_log: LogFn | None = None) -> CheckResult:
    missing: list[str] = []
    stopped: list[str] = []
    details: list[str] = []
    for name in OS_VPN_SERVICES:
        status, start = _service_info(name)
        details.append(f"{name}={status}/{start}")
        if status == "MISSING":
            missing.append(name)
        elif status != "RUNNING":
            stopped.append(name)
    tech = "; ".join(details)
    if missing:
        return CheckResult(
            "os_vpn_services",
            "연결 지원 기능",
            "pc_issue",
            "VPN 연결에 필요한 Windows 기능이 없습니다.",
            tech,
            "관리자에게 PC 점검·복구를 요청해 주세요.",
        )
    if stopped:
        return CheckResult(
            "os_vpn_services",
            "연결 지원 기능",
            "suspect",
            "VPN 연결을 돕는 Windows 기능이 꺼져 있을 수 있습니다.",
            tech,
            "PC를 다시 시작한 뒤 연결을 재시도해 주세요.",
        )
    return CheckResult(
        "os_vpn_services",
        "연결 지원 기능",
        "ok",
        "VPN 연결 지원 기능이 준비되어 있습니다.",
        tech,
    )


def check_vpn_adapter(_log: LogFn | None = None) -> CheckResult:
    ok, status = _vpn_adapter_ok()
    tech = f"{VPN_ADAPTER_NAME}={status}"
    if ok:
        return CheckResult(
            "vpn_adapter",
            "VPN 연결 장치",
            "ok",
            "VPN 연결에 사용하는 장치가 확인되었습니다.",
            tech,
        )
    return CheckResult(
        "vpn_adapter",
        "VPN 연결 장치",
        "pc_issue",
        "VPN 연결에 사용되는 네트워크 장치에 문제가 있습니다.",
        tech,
        "VPN 프로그램을 다시 실행해 보세요. 장치 복구가 필요하면 관리자에게 문의하세요.",
        fix_action="restart_client",
    )


def check_internet_basic(_log: LogFn | None = None) -> CheckResult:
    code, out = _run(["ping", "-n", "2", "-w", "2000", "8.8.8.8"], timeout=10)
    ok = code == 0 and ("TTL=" in out or "ttl=" in out)
    tech = out.strip().splitlines()[-1] if out.strip() else f"code={code}"
    if ok:
        return CheckResult(
            "internet_basic",
            "인터넷 연결",
            "ok",
            "기본 인터넷 연결이 가능합니다.",
            tech,
        )
    return CheckResult(
        "internet_basic",
        "인터넷 연결",
        "pc_issue",
        "인터넷 연결이 원활하지 않은 것 같습니다.",
        tech,
        "유선/Wi-Fi를 확인한 뒤 다시 시도해 주세요.",
        blocks_followup=True,
    )


def check_proxy_settings(_log: LogFn | None = None) -> CheckResult:
    import winreg

    enabled = False
    server = ""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            try:
                enabled = bool(winreg.QueryValueEx(key, "ProxyEnable")[0])
            except OSError:
                pass
            try:
                server = str(winreg.QueryValueEx(key, "ProxyServer")[0])
            except OSError:
                pass
    except OSError as exc:
        return CheckResult(
            "proxy_settings",
            "프록시 설정",
            "suspect",
            "프록시 설정을 확인하지 못했습니다.",
            str(exc),
        )
    tech = f"ProxyEnable={enabled}, ProxyServer={server or '(none)'}"
    code, winhttp = _run(["netsh", "winhttp", "show", "proxy"], timeout=8)
    tech += f" | winhttp: {winhttp.strip()[:120]}"
    if enabled and server:
        return CheckResult(
            "proxy_settings",
            "프록시 설정",
            "suspect",
            "프록시가 켜져 있어 VPN·로그인에 영향을 줄 수 있습니다.",
            tech,
            "회사 안내대로 프록시를 확인하세요. 임의 변경이 어려우면 관리자에게 문의하세요.",
        )
    return CheckResult(
        "proxy_settings",
        "프록시 설정",
        "ok",
        "사용자 프록시에 특별한 이상은 없습니다.",
        tech,
    )


def check_routing_default(_log: LogFn | None = None) -> CheckResult:
    code, out = _run(["route", "print", "0.0.0.0"], timeout=10)
    tech = "\n".join(out.splitlines()[:15])
    if "0.0.0.0" in out and code == 0:
        return CheckResult(
            "routing_default",
            "기본 경로",
            "ok",
            "기본 인터넷 경로가 확인되었습니다. (VPN 정책에 따라 경로가 달라질 수 있습니다)",
            tech,
        )
    return CheckResult(
        "routing_default",
        "기본 경로",
        "suspect",
        "기본 경로를 명확히 확인하지 못했습니다.",
        tech,
    )


def check_vpn_fqdn_config(_log: LogFn | None = None) -> CheckResult:
    from app.resolve import resolve_vpn_fqdn

    host, source = resolve_vpn_fqdn()
    if host:
        src = "사용자 정보에 입력한 도메인" if source == "user_info" else "설정 파일"
        return CheckResult(
            "vpn_fqdn_config",
            "VPN 주소",
            "ok",
            f"점검에 사용할 VPN 주소: {host} ({src})",
            f"{host} via {source}",
        )
    return CheckResult(
        "vpn_fqdn_config",
        "VPN 주소",
        "skip",
        "VPN 접속 도메인이 없습니다. 「사용자 정보」에 도메인을 입력하면 서버 접근을 점검합니다.",
        "user_info.vpn_domain / config.vpn_fqdn empty",
        "사용자 정보에서 VPN 접속 도메인을 저장한 뒤 다시 점검해 주세요.",
        blocks_followup=True,
    )


def check_dns_vpn(_log: LogFn | None = None) -> CheckResult:
    from app.resolve import resolve_vpn_fqdn

    host, _src = resolve_vpn_fqdn()
    if not host:
        return CheckResult(
            "dns_vpn",
            "VPN 주소 이름 조회",
            "skip",
            "VPN 주소가 없어 이름 조회를 건너뛰었습니다.",
            "",
            blocks_followup=True,
        )
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
        return CheckResult(
            "dns_vpn",
            "VPN 주소 이름 조회",
            "ok",
            f"VPN 서버 이름 조회에 성공했습니다. ({host})",
            f"{host} -> {', '.join(ips[:3])}",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "dns_vpn",
            "VPN 주소 이름 조회",
            "pc_issue",
            f"VPN 서버 이름({host})을 찾지 못했습니다.",
            str(exc),
            "네트워크·DNS를 확인하거나, 입력한 도메인이 맞는지 확인해 주세요.",
            blocks_followup=True,
        )


def check_https_vpn(_log: LogFn | None = None) -> CheckResult:
    from app.resolve import resolve_vpn_fqdn

    host, _src = resolve_vpn_fqdn()
    if not host:
        return CheckResult(
            "https_vpn",
            "VPN 서버 보안 연결",
            "skip",
            "VPN 주소가 없어 HTTPS 점검을 건너뛰었습니다.",
            "",
        )
    url = f"https://{host}/"
    try:
        ctx = ssl.create_default_context()
        req = Request(url, method="GET")
        with urlopen(req, timeout=10, context=ctx) as resp:  # noqa: S310
            code = getattr(resp, "status", 200)
        return CheckResult(
            "https_vpn",
            "VPN 서버 보안 연결",
            "ok",
            "VPN 서버와의 보안 연결(HTTPS)이 가능합니다.",
            f"GET {url} -> {code}",
        )
    except ssl.SSLError as exc:
        return CheckResult(
            "https_vpn",
            "VPN 서버 보안 연결",
            "suspect",
            "VPN 서버 인증서/보안 연결에 문제가 있을 수 있습니다.",
            str(exc),
            "결과를 저장해 관리자에게 전달해 주세요. (서버 HTTPS 인증서는 설치 파일 서명과 별개입니다)",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "https_vpn",
            "VPN 서버 보안 연결",
            "pc_issue",
            "VPN 서버에 보안 연결을 할 수 없습니다.",
            str(exc),
            "네트워크·방화벽·프록시를 확인하세요. 계속되면 관리자에게 문의하세요.",
        )


def check_dns_public(_log: LogFn | None = None) -> CheckResult:
    host = "www.microsoft.com"
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
        return CheckResult(
            "dns_public",
            "인터넷 이름 조회",
            "ok",
            "인터넷 주소 조회가 정상입니다.",
            f"{host} -> {', '.join(ips[:3])}",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "dns_public",
            "인터넷 이름 조회",
            "pc_issue",
            "인터넷 주소 조회에 문제가 있습니다.",
            str(exc),
            "DNS/네트워크를 확인한 뒤 다시 시도해 주세요.",
        )


def check_internal_target_config(_log: LogFn | None = None) -> CheckResult:
    cfg = load_config()
    if cfg.internal_test_hosts:
        return CheckResult(
            "internal_target_config",
            "내부 점검 대상",
            "ok",
            "내부 시스템 점검 대상이 등록되어 있습니다.",
            ", ".join(cfg.internal_test_hosts[:5]),
        )
    return CheckResult(
        "internal_target_config",
        "내부 점검 대상",
        "skip",
        "접속할 회사 시스템 주소가 등록되지 않아 내부 접속 점검을 건너뜁니다.",
        "resources/config.json internal_test_hosts 비어 있음",
        "관리자에게 점검용 내부 주소를 등록해 달라고 요청하세요.",
        blocks_followup=True,
    )


def check_dns_internal(_log: LogFn | None = None) -> CheckResult:
    cfg = load_config()
    if not cfg.internal_test_hosts:
        return CheckResult(
            "dns_internal",
            "회사 주소 이름 조회",
            "skip",
            "내부 점검 대상이 없어 건너뛰었습니다.",
            "",
            blocks_followup=True,
        )
    host = cfg.internal_test_hosts[0]
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
        return CheckResult(
            "dns_internal",
            "회사 주소 이름 조회",
            "ok",
            "회사 시스템 이름 조회에 성공했습니다.",
            f"{host} -> {', '.join(ips[:3])}",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "dns_internal",
            "회사 주소 이름 조회",
            "pc_issue",
            "회사 시스템 이름을 찾지 못했습니다.",
            str(exc),
            "VPN 연결 상태와 DNS를 확인하세요. 계속되면 관리자에게 문의하세요.",
            blocks_followup=True,
        )


def check_https_internal(_log: LogFn | None = None) -> CheckResult:
    cfg = load_config()
    if not cfg.internal_test_hosts:
        return CheckResult(
            "https_internal",
            "회사 시스템 접속",
            "skip",
            "내부 점검 대상이 없어 건너뛰었습니다.",
            "",
        )
    host = cfg.internal_test_hosts[0]
    url = f"https://{host}/" if "://" not in host else host
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            code = getattr(resp, "status", 200)
        return CheckResult(
            "https_internal",
            "회사 시스템 접속",
            "ok",
            "등록된 회사 시스템에 연결이 가능합니다.",
            f"{url} -> {code}",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "https_internal",
            "회사 시스템 접속",
            "suspect",
            "회사 시스템 접속에 실패했습니다. 권한·방화벽은 관리자 확인이 필요할 수 있습니다.",
            str(exc),
            "진단 결과를 저장해 관리자에게 전달해 주세요.",
        )


def check_auth_failure_hint(_log: LogFn | None = None) -> CheckResult:
    return CheckResult(
        "auth_failure_hint",
        "로그인(ID/PW·OTP) 안내",
        "needs_admin",
        "로그인 화면은 보이지만 인증이 거부되는 경우, PC에서 자동 복구할 수 없습니다.",
        "APM/AD/LDAP/RADIUS/SAML — admin review",
        "오류 화면을 캡처하고 진단 결과를 저장해 관리자에게 전달해 주세요.",
    )


def check_session_admin_hint(_log: LogFn | None = None) -> CheckResult:
    return CheckResult(
        "session_admin_hint",
        "서버 세션 종료",
        "needs_admin",
        "서버 정책·세션 타임아웃으로 끊긴 경우는 PC에서 해결할 수 없습니다.",
        "APM session vs tunnel drop",
        "끊긴 시각과 진단 결과를 저장해 관리자에게 전달해 주세요.",
    )


def check_tunnel_policy_hint(_log: LogFn | None = None) -> CheckResult:
    cfg = load_config()
    if cfg.internet_allowed_on_vpn is False:
        return CheckResult(
            "tunnel_policy_hint",
            "인터넷 정책",
            "needs_admin",
            "이 환경은 VPN 연결 후 외부 인터넷이 제한될 수 있습니다. 오류가 아닐 수 있습니다.",
            f"tunnel_mode={cfg.tunnel_mode}",
            "업무에 필요한 사이트만 접속되는지 확인하고, 정책 확인은 관리자에게 문의하세요.",
        )
    if cfg.tunnel_mode == "unknown" or cfg.internet_allowed_on_vpn is None:
        return CheckResult(
            "tunnel_policy_hint",
            "인터넷 정책",
            "skip",
            "VPN 터널 방식(전체/분할)·인터넷 허용 여부가 등록되지 않아 정책 판단을 건너뜁니다.",
            "config tunnel_mode / internet_allowed_on_vpn",
        )
    return CheckResult(
        "tunnel_policy_hint",
        "인터넷 정책",
        "ok",
        "등록된 정책상 VPN 후 인터넷이 허용되는 구성입니다.",
        f"tunnel_mode={cfg.tunnel_mode}",
    )


def check_acl_admin_hint(_log: LogFn | None = None) -> CheckResult:
    return CheckResult(
        "acl_admin_hint",
        "접근 권한",
        "needs_admin",
        "특정 시스템만 안 되면 권한·방화벽·서버 문제일 수 있어 PC에서 해결할 수 없습니다.",
        "BIG-IP ACL / internal firewall",
        "접속하려는 주소와 진단 결과를 저장해 관리자에게 전달해 주세요.",
    )


def check_security_soft_hint(_log: LogFn | None = None) -> CheckResult:
    return CheckResult(
        "security_soft_hint",
        "보안·프록시 프로그램",
        "suspect",
        "보안/프록시 프로그램과의 충돌 여부는 추가 확인이 필요할 수 있습니다.",
        "manual review",
        "문제가 반복되면 관리자에게 예외 등록을 요청해 주세요. 보안 기능을 끄지 마세요.",
    )


def check_error_message_hint(_log: LogFn | None = None) -> CheckResult:
    """Branch by user-entered error text (symptom field)."""
    from app.user_info import get_user_info

    text = (get_user_info().symptom or "").strip()
    if not text:
        return CheckResult(
            "error_message_hint",
            "오류 메시지",
            "skip",
            "오류 문구가 없습니다. 「사용자 정보」의 증상/오류 메시지에 화면에 보인 문구를 적어 주세요.",
            "",
            "오류 문구를 저장한 뒤 다시 점검하면 더 정확한 안내를 받을 수 있습니다.",
        )
    low = text.lower()
    if "서버에 연결할 수 없" in text or "cannot connect" in low:
        return CheckResult(
            "error_message_hint",
            "오류 메시지 분류",
            "suspect",
            "「서버에 연결할 수 없습니다」로 보입니다. 주소·DNS·HTTPS·TLS를 함께 확인합니다.",
            text[:200],
            "아래 서버 접근 점검 결과를 확인하세요. TLS 1.2만의 문제로 단정하지 않습니다.",
        )
    if "연결 장치" in text or "network access" in low:
        return CheckResult(
            "error_message_hint",
            "오류 메시지 분류",
            "pc_issue",
            "「네트워크 접속 연결 장치를 찾을 수 없습니다」로 보입니다.",
            text[:200],
            "구성 요소·서비스를 확인하세요. 복구가 필요하면 관리자에게 문의하세요.",
            fix_action="restart_client",
        )
    if "해지" in text or "revocation" in low or "crl" in low:
        return CheckResult(
            "error_message_hint",
            "오류 메시지 분류",
            "needs_admin",
            "인증서 해지 확인 오류로 보입니다. 해지 확인을 끄는 방법은 권장하지 않습니다.",
            text[:200],
            "진단 결과를 저장해 관리자에게 전달해 주세요.",
        )
    if "초기화" in text:
        return CheckResult(
            "error_message_hint",
            "오류 메시지 분류",
            "suspect",
            "「초기화 중」 관련 문구입니다. ‘초기화 중에서 멈춰요’ 메뉴로 점검하는 것이 더 정확합니다.",
            text[:200],
            "이슈 목록에서 「초기화 중에서 멈춰요」를 선택해 주세요.",
        )
    return CheckResult(
        "error_message_hint",
        "오류 메시지 분류",
        "needs_admin",
        "입력하신 오류 문구를 수집했습니다. 알려진 자동 분기 규칙에 해당하지 않습니다.",
        text[:200],
        "진단 결과를 저장해 관리자에게 전달해 주세요.",
    )


def check_tunnel_init_hint(_log: LogFn | None = None) -> CheckResult:
    return CheckResult(
        "tunnel_init_hint",
        "초기화 중 안내",
        "suspect",
        "「초기화 중」은 연결 시도 이후 터널을 만드는 단계에서 멈춘 증상입니다. "
        "PC 구성요소·서비스 문제일 수도 있고, 서버(BIG-IP) 측 원인일 수도 있습니다.",
        "guide p11/17 + F5 lifecycle",
        "아래 점검 후 이상이 없으면 결과를 저장해 관리자에게 전달하세요. "
        "네트워크 초기화는 사용자 화면에서 자동 실행하지 않습니다.",
    )


def check_wan_miniport_hint(_log: LogFn | None = None) -> CheckResult:
    # Soft presence via RAS enum registry
    import winreg

    present = 0
    base = r"SYSTEM\CurrentControlSet\Enum\SWD\MSRRAS"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
            i = 0
            while True:
                try:
                    winreg.EnumKey(root, i)
                    present += 1
                except OSError:
                    break
                i += 1
    except OSError:
        present = -1
    tech = f"MSRRAS children={present}"
    if present < 0:
        return CheckResult(
            "wan_miniport_hint",
            "연결용 네트워크 장치",
            "suspect",
            "연결용 네트워크 장치 목록을 확인하지 못했습니다.",
            tech,
        )
    if present == 0:
        return CheckResult(
            "wan_miniport_hint",
            "연결용 네트워크 장치",
            "pc_issue",
            "VPN 연결에 쓰는 Windows 네트워크 장치가 보이지 않습니다.",
            tech,
            "관리자에게 장치/드라이버 복구를 요청해 주세요. (사용자 화면에서 일괄 삭제는 하지 않습니다)",
        )
    return CheckResult(
        "wan_miniport_hint",
        "연결용 네트워크 장치",
        "ok",
        "연결용 Windows 네트워크 장치 항목이 확인되었습니다.",
        tech,
    )


def check_bigip_possible_hint(_log: LogFn | None = None) -> CheckResult:
    return CheckResult(
        "bigip_possible_hint",
        "서버 측 확인",
        "needs_admin",
        "PC에서 명확한 원인이 없으면 BIG-IP(서버) 로그·세션 확인이 필요할 수 있습니다.",
        "do not assume PC-only",
        "진단 결과를 저장해 관리자에게 전달해 주세요.",
    )


def check_latency_dns(_log: LogFn | None = None) -> CheckResult:
    host = "www.microsoft.com"
    times: list[float] = []
    err = ""
    for _ in range(3):
        t0 = time.perf_counter()
        try:
            socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            times.append((time.perf_counter() - t0) * 1000)
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            break
    if not times:
        return CheckResult(
            "latency_dns",
            "DNS 응답 시간",
            "pc_issue",
            "이름 조회에 실패해 속도 측정을 할 수 없습니다.",
            err,
        )
    avg = sum(times) / len(times)
    tech = f"samples_ms={[round(t, 1) for t in times]} avg={avg:.1f}"
    if avg > 500:
        return CheckResult(
            "latency_dns",
            "DNS 응답 시간",
            "suspect",
            f"이름 조회가 다소 느립니다 (평균 {avg:.0f}ms).",
            tech,
            "네트워크 상태를 확인하세요. VPN만의 원인은 아닐 수 있습니다.",
        )
    return CheckResult(
        "latency_dns",
        "DNS 응답 시간",
        "ok",
        f"이름 조회 시간 평균 {avg:.0f}ms 입니다.",
        tech,
    )


def check_latency_https(_log: LogFn | None = None) -> CheckResult:
    url = "https://www.microsoft.com/"
    times: list[float] = []
    last = ""
    for _ in range(2):
        t0 = time.perf_counter()
        try:
            req = Request(url, method="HEAD")
            with urlopen(req, timeout=12) as resp:  # noqa: S310
                last = str(getattr(resp, "status", ""))
            times.append((time.perf_counter() - t0) * 1000)
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            break
    if not times:
        return CheckResult(
            "latency_https",
            "HTTPS 응답 시간",
            "suspect",
            "보안 연결 응답 시간을 측정하지 못했습니다.",
            last,
        )
    avg = sum(times) / len(times)
    tech = f"samples_ms={[round(t, 1) for t in times]} avg={avg:.1f} last={last}"
    if avg > 3000:
        return CheckResult(
            "latency_https",
            "HTTPS 응답 시간",
            "suspect",
            f"웹 응답이 느립니다 (평균 {avg:.0f}ms). VPN만의 원인이라고 단정할 수 없습니다.",
            tech,
            "동일 시간대에 정상 PC와 비교하거나, 결과를 저장해 관리자에게 전달하세요.",
        )
    return CheckResult(
        "latency_https",
        "HTTPS 응답 시간",
        "ok",
        f"웹 응답 시간 평균 {avg:.0f}ms 입니다.",
        tech,
    )


CHECKS: dict[str, Callable[[LogFn | None], CheckResult]] = {
    "install_presence": check_install_presence,
    "component_files": check_component_files,
    "client_binary": check_client_binary,
    "installer_signature": check_installer_signature,
    "cert_sectigo_chain": check_cert_sectigo_chain,
    "windows_installer": check_windows_installer,
    "leftover_install": check_leftover_install,
    "admin_elevation": check_admin_elevation,
    "f5_services": check_f5_services,
    "os_vpn_services": check_os_vpn_services,
    "vpn_adapter": check_vpn_adapter,
    "internet_basic": check_internet_basic,
    "proxy_settings": check_proxy_settings,
    "routing_default": check_routing_default,
    "vpn_fqdn_config": check_vpn_fqdn_config,
    "dns_vpn": check_dns_vpn,
    "https_vpn": check_https_vpn,
    "dns_public": check_dns_public,
    "internal_target_config": check_internal_target_config,
    "dns_internal": check_dns_internal,
    "https_internal": check_https_internal,
    "auth_failure_hint": check_auth_failure_hint,
    "session_admin_hint": check_session_admin_hint,
    "tunnel_policy_hint": check_tunnel_policy_hint,
    "acl_admin_hint": check_acl_admin_hint,
    "security_soft_hint": check_security_soft_hint,
    "error_message_hint": check_error_message_hint,
    "tunnel_init_hint": check_tunnel_init_hint,
    "wan_miniport_hint": check_wan_miniport_hint,
    "bigip_possible_hint": check_bigip_possible_hint,
    "latency_dns": check_latency_dns,
    "latency_https": check_latency_https,
}

# If predecessor failed with blocks_followup, skip these
_FOLLOWUPS: dict[str, tuple[str, ...]] = {
    "vpn_fqdn_config": ("dns_vpn", "https_vpn"),
    "dns_vpn": ("https_vpn",),
    "internal_target_config": ("dns_internal", "https_internal"),
    "dns_internal": ("https_internal",),
    "internet_basic": (),
}


def run_diagnosis(
    symptom_id: str,
    symptom_title: str,
    check_ids: list[str] | tuple[str, ...],
    log: LogFn | None = None,
) -> DiagnosisReport:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    report = DiagnosisReport(
        symptom_id=symptom_id,
        symptom_title=symptom_title,
        started_at=started,
    )
    skip_ids: set[str] = set()
    for cid in check_ids:
        if cid in skip_ids:
            report.results.append(
                CheckResult(
                    cid,
                    cid,
                    "skip",
                    "앞선 점검 실패로 이 항목은 실행하지 않았습니다.",
                    "blocked by prior failure",
                )
            )
            continue
        fn = CHECKS.get(cid)
        if not fn:
            report.results.append(
                CheckResult(cid, cid, "skip", "점검을 건너뛰었습니다.", "unknown check")
            )
            continue
        if log:
            log(f"점검 중: {cid}")
        try:
            result = fn(log)
        except Exception as exc:  # noqa: BLE001
            result = CheckResult(cid, cid, "suspect", "점검 중 오류가 발생했습니다.", str(exc))
        report.results.append(result)
        if result.blocks_followup and result.status in ("pc_issue", "skip"):
            for dep in _FOLLOWUPS.get(cid, ()):
                skip_ids.add(dep)
    report.finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
    return report


def save_diagnosis_report(report: DiagnosisReport, log: LogFn | None = None) -> Path:
    base = troubleshoot_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"diagnosis_{report.symptom_id}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    lines = [
        f"Symptom: {report.symptom_title} ({report.symptom_id})",
        f"Started: {report.started_at}",
        f"Finished: {report.finished_at}",
        f"Headline: {report.headline()}",
        "",
        "===== User-facing =====",
    ]
    for r in report.results:
        lines.append(f"[{r.status}] {r.user_label}: {r.user_detail}")
    lines.append("")
    lines.append("===== Technical =====")
    for r in report.results:
        lines.append(f"[{r.status}] {r.id}: {r.tech_detail}")
    lines.append("")
    lines.append("===== Recommended =====")
    lines.append(report.recommended_fix())
    path.write_text("\n".join(lines), encoding="utf-8-sig")
    if log:
        log(f"진단 결과 저장: {path}")
    return path


def safe_restart_edge_client(log: LogFn) -> bool:
    log("VPN 프로그램을 종료한 뒤 다시 실행합니다…")
    for name in ("f5fpclientW.exe", "f5fpc.exe", "f5vpn.exe"):
        run_silent(["taskkill", "/F", "/IM", name], timeout=10)
    time.sleep(1)
    if F5_VPN_CLIENT.exists():
        try:
            from app.winproc import popen_silent

            popen_silent([str(F5_VPN_CLIENT)], cwd=str(F5_VPN_CLIENT.parent))
            log("VPN 프로그램을 다시 실행했습니다.")
            return True
        except Exception as exc:  # noqa: BLE001
            log(f"다시 실행 실패: {exc}")
            return False
    log("실행 파일을 찾을 수 없습니다.")
    return False
