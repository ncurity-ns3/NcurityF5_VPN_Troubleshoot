"""Atomic troubleshooting actions (from VPN_Troubleshooting.bat + user issue guide)."""

from __future__ import annotations

import ctypes
import locale
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.paths import resource_path, troubleshoot_dir

LogFn = Callable[[str], None]


def _console_encoding() -> str:
    """Console tool output encoding.

    On Korean Windows, ipconfig/route/sc still emit OEM code page (cp949),
    even when Python runs in UTF-8 mode.
    """
    if sys.platform == "win32":
        try:
            oem = int(ctypes.windll.kernel32.GetOEMCP())
            if oem:
                return f"cp{oem}"
        except Exception:  # noqa: BLE001
            pass
        return "cp949"
    enc = locale.getpreferredencoding(False) or "utf-8"
    return enc


def _decode_console(data: bytes | None) -> str:
    if not data:
        return ""
    # Prefer OEM/cp949 before utf-8 so Korean console tools decode correctly
    candidates = [_console_encoding(), "cp949", "utf-8"]
    seen: set[str] = set()
    fallback = ""
    for enc in candidates:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if any("\uac00" <= ch <= "\ud7a3" for ch in text):
            return text
        if not fallback:
            fallback = text
    if fallback:
        return fallback
    return data.decode(_console_encoding(), errors="replace")

MINIPORT_IDS = [
    r"SWD\MSRRAS\MS_NDISWANIP",
    r"SWD\MSRRAS\MS_NDISWANIPV6",
    r"SWD\MSRRAS\MS_L2TPMINIPORT",
    r"SWD\MSRRAS\MS_PPPOEMINIPORT",
    r"SWD\MSRRAS\MS_PPTPMINIPORT",
    r"SWD\MSRRAS\MS_SSTPMINIPORT",
    r"SWD\MSRRAS\MS_AGILEVPNMINIPORT",
    r"SWD\MSRRAS\MS_NDISWANBH",
]

VPN_SERVICES = ["RasMan", "TapiSrv", "SstpSvc"]
EDGE_CLIENT_DIR = Path(r"C:\Program Files (x86)\F5 Networks\Edge Client")


@dataclass
class ActionResult:
    ok: bool
    message: str = ""


def _run(
    cmd: list[str] | str,
    log: LogFn,
    *,
    shell: bool = False,
    timeout: int | None = None,
    cwd: str | Path | None = None,
) -> ActionResult:
    display = cmd if isinstance(cmd, str) else " ".join(cmd)
    log(f"실행: {display}")
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        proc = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            creationflags=0 if shell else flags,
        )
        out = _decode_console(proc.stdout).strip()
        err = _decode_console(proc.stderr).strip()
        if out:
            for line in out.splitlines()[-40:]:
                log(f"  {line}")
            if err:
                for line in err.splitlines()[-20:]:
                    log(f"  {line}")
        if proc.returncode == 0:
            return ActionResult(True, out)
        return ActionResult(False, err or f"exit={proc.returncode}")
    except subprocess.TimeoutExpired:
        log("  시간 초과")
        return ActionResult(False, "timeout")
    except Exception as exc:  # noqa: BLE001
        log(f"  오류: {exc}")
        return ActionResult(False, str(exc))


def ensure_work_folder(log: LogFn) -> ActionResult:
    path = troubleshoot_dir()
    log(f"작업 폴더를 준비했습니다: {path}")
    return ActionResult(True, str(path))


def collect_client_info(log: LogFn, os_note: str = "") -> ActionResult:
    from app.user_info import get_user_info

    base = troubleshoot_dir()
    user = os.environ.get("USERNAME", "user")
    info_path = base / f"{user}_ClientInfo.txt"
    log("환경 정보를 수집하고 있습니다…")

    parts: list[str] = []
    ver = subprocess.run("ver", shell=True, capture_output=True)
    parts.append(_decode_console(ver.stdout).strip())
    parts.append(f"Date/Time : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    parts.append("-" * 40)

    case = get_user_info()
    if case.user_id or case.issue_time or case.vpn_domain:
        parts.append(case.to_text())
    else:
        parts.append("===== 사용자 정보 =====")
        parts.append("(미입력)")
        parts.append("")
        log("사용자 정보가 없습니다. [사용자 정보]에서 입력해 주세요.")

    note = os_note or case.os_note
    if note:
        parts.append("===== OS Version =====")
        parts.append(f"OS Version : {note}")
        parts.append("")

    for label, cmd in [
        ("ipconfig /all", ["ipconfig", "/all"]),
        ("route print", ["route", "print"]),
    ]:
        log(f"수집 중: {label}")
        r = subprocess.run(cmd, capture_output=True)
        parts.append(f"===== {label} =====")
        parts.append(_decode_console(r.stdout))
        parts.append("")

    info_path.write_text("\n".join(parts), encoding="utf-8-sig")
    log(f"저장 완료: {info_path}")
    return ActionResult(True, str(info_path))


def _kill_f5wininfo() -> None:
    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "f5wininfo.exe"],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        pass


def _f5_work_dir() -> Path:
    try:
        path = troubleshoot_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        path = Path(os.environ.get("TEMP", os.getcwd())) / "F5_SSL_VPN_Troubleshoot"
        path.mkdir(parents=True, exist_ok=True)
        return path


def _prepare_f5wininfo(log: LogFn | None = None) -> Path | None:
    src = resource_path("tools", "f5wininfo.exe")
    if not src.exists():
        return None
    work = _f5_work_dir()
    dest = work / "f5wininfo.exe"
    try:
        need_copy = (
            (not dest.exists())
            or dest.stat().st_size != src.stat().st_size
            or dest.stat().st_mtime < src.stat().st_mtime
        )
        if need_copy:
            _kill_f5wininfo()
            time.sleep(0.5)
            shutil.copy2(src, dest)
        return dest
    except Exception as exc:
        if log:
            log(f"작업 폴더 복사에 실패해 원본으로 실행합니다: {exc}")
        return src


def _delete_incomplete_report(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size == 0:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def _terminate_proc(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    _kill_f5wininfo()


def collect_f5_logs(log: LogFn) -> ActionResult:
    """Generate one HTML report via f5wininfo.

    /full hangs on many PCs. Use:
      /report /NAReport /RAReport /html
    (Command-Line Utilities, OPSWAT, network diagnostics)

    Output file stays 0 bytes until the process exits.
    """
    from app.user_info import get_user_info

    # NA+RA typically ~3.5 minutes
    report_timeout = 480.0
    exe = _prepare_f5wininfo(log)
    if exe is None:
        log("f5wininfo.exe 파일을 찾을 수 없습니다.")
        return ActionResult(False, "f5wininfo missing")

    base = troubleshoot_dir()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    case = get_user_info()
    tag = case.user_id.strip() if case.user_id.strip() else os.environ.get("USERNAME", "user")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag) or "user"
    out_path = base / f"F5_Report_{safe}_{stamp}.html"

    log("F5 로그를 생성하고 있습니다…")
    log("완료까지 수 분 정도 걸릴 수 있습니다.")
    _kill_f5wininfo()
    time.sleep(0.3)

    proc: subprocess.Popen[bytes] | None = None
    try:
        # Allow f5wininfo UI ("Collecting data") — hiding the window can hang collection.
        cmd = [str(exe), "/report", "/NAReport", "/RAReport", "/html", str(out_path)]
        proc = subprocess.Popen(
            cmd,
            cwd=str(exe.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + report_timeout
        last_log = 0.0
        started = time.monotonic()
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            now = time.monotonic()
            if now - last_log >= 15.0:
                log(f"수집 중… {int(now - started)}초 경과")
                last_log = now
            time.sleep(1.0)
        else:
            log("시간 초과 — 프로세스를 종료합니다.")
            _terminate_proc(proc)
            proc = None
            time.sleep(0.5)
            _delete_incomplete_report(out_path)
            log("F5 로그 생성에 실패했습니다.")
            return ActionResult(False, "timeout")

        time.sleep(0.5)
        try:
            ok = out_path.exists() and out_path.stat().st_size > 0
        except OSError:
            ok = False

        if ok:
            log(f"완료: {out_path.name} ({out_path.stat().st_size:,} bytes)")
            log(f"저장 위치: {base}")
            return ActionResult(True, str(out_path))

        _delete_incomplete_report(out_path)
        log("F5 로그 생성에 실패했습니다.")
        return ActionResult(False, "report failed")
    except Exception as exc:  # noqa: BLE001
        _terminate_proc(proc)
        time.sleep(0.5)
        _delete_incomplete_report(out_path)
        log(f"실패: {exc}")
        return ActionResult(False, str(exc))
    finally:
        if proc is not None and proc.poll() is None:
            _terminate_proc(proc)


def remove_edge_client(log: LogFn) -> ActionResult:
    """Run f5wininfo.exe /r and wait until Edge Client folder is gone."""
    exe = _prepare_f5wininfo(log)
    if exe is None:
        log("f5wininfo.exe 파일을 찾을 수 없습니다.")
        return ActionResult(False, "f5wininfo missing")
    if not exe.exists():
        log("f5wininfo.exe 파일을 찾을 수 없습니다.")
        return ActionResult(False, "f5wininfo missing")

    log("브라우저를 모두 종료한 뒤 진행해 주세요.")
    log("Edge Client를 삭제하고 있습니다. 잠시만 기다려 주세요…")
    try:
        subprocess.Popen(
            [str(exe), "/r"],
            cwd=str(exe.parent),
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as exc:  # noqa: BLE001
        log(f"실행에 실패했습니다: {exc}")
        return ActionResult(False, str(exc))

    for sec in range(1, 301):
        if not EDGE_CLIENT_DIR.exists():
            log(f"Edge Client 삭제가 완료되었습니다. ({sec}초)")
            return ActionResult(True)
        if sec % 5 == 0:
            log(f"삭제 진행 중… {sec}초")
        time.sleep(1)

    if EDGE_CLIENT_DIR.exists():
        log("삭제 확인 시간이 초과되었습니다. Edge Client가 아직 남아 있을 수 있습니다.")
        return ActionResult(False, "timeout")
    return ActionResult(True)


def open_f5wininfo(log: LogFn) -> ActionResult:
    exe = _prepare_f5wininfo(log)
    if exe is None:
        log("f5wininfo.exe 파일을 찾을 수 없습니다.")
        return ActionResult(False, "f5wininfo missing")
    if not exe.exists():
        log("f5wininfo.exe 파일을 찾을 수 없습니다.")
        return ActionResult(False, "missing")
    log("f5wininfo를 실행합니다.")
    subprocess.Popen([str(exe)], cwd=str(exe.parent))
    return ActionResult(True)


def list_miniports(log: LogFn) -> ActionResult:
    ids = ",".join(f"'{x}'" for x in MINIPORT_IDS)
    ps = (
        "Get-PnpDevice -Class Net | "
        f"Where-Object {{ $_.InstanceId -in @({ids}) }} | "
        "Select-Object Status,FriendlyName,InstanceId | Format-Table -AutoSize | Out-String"
    )
    return _run(["powershell", "-NoProfile", "-Command", ps], log)


def remove_miniports(log: LogFn) -> ActionResult:
    log("WAN Miniport 삭제 전 상태를 확인합니다.")
    list_miniports(log)
    ok_all = True
    for mid in MINIPORT_IDS:
        r = _run(["pnputil", "/remove-device", mid], log)
        if not r.ok:
            pass
    log("WAN Miniport 삭제 후 상태를 확인합니다.")
    list_miniports(log)
    return ActionResult(ok_all)


def rescan_devices(log: LogFn) -> ActionResult:
    log("네트워크 어댑터를 다시 검색합니다.")
    r = _run(["pnputil", "/scan-devices"], log)
    time.sleep(5)
    list_miniports(log)
    return r


def restart_vpn_services(log: LogFn) -> ActionResult:
    log("VPN 관련 서비스를 중지합니다.")
    for name in VPN_SERVICES:
        _run(["sc", "stop", name], log)
        _wait_service(name, "STOPPED", log)

    log("VPN 관련 서비스를 시작합니다.")
    for name in VPN_SERVICES:
        _run(["sc", "start", name], log)
        _wait_service(name, "RUNNING", log)
    return ActionResult(True)


def _wait_service(name: str, goal: str, log: LogFn, retries: int = 30) -> None:
    for _ in range(retries):
        r = subprocess.run(["sc", "query", name], capture_output=True)
        if goal in _decode_console(r.stdout):
            log(f"  {name}: {goal}")
            return
        time.sleep(1)
    log(f"  {name}: 상태 확인 시간 초과")


def run_sfc(log: LogFn) -> ActionResult:
    log("시스템 파일 검사를 시작합니다. 완료까지 시간이 걸릴 수 있습니다.")
    r = _run(["sfc", "/scannow"], log, timeout=3600)
    log_path = troubleshoot_dir() / "f5win_troubleshoot_result.txt"
    cbs = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Logs" / "CBS" / "CBS.log"
    if cbs.exists():
        ps = (
            f"Select-String -Path '{cbs}' -Pattern '\\[SR\\]' -Encoding UTF8 | "
            "Select-Object -Last 100 | ForEach-Object {{ $_.Line }} | "
            f"Out-File -FilePath '{log_path}' -Append -Encoding utf8"
        )
        _run(["powershell", "-NoProfile", "-Command", ps], log)
    return r


def run_dism_scan(log: LogFn) -> ActionResult:
    log("Windows 이미지 검사를 시작합니다.")
    return _run(["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"], log, timeout=3600)


def run_dism_restore(log: LogFn) -> ActionResult:
    log("Windows 이미지 복구를 시작합니다. 완료까지 시간이 걸릴 수 있습니다.")
    return _run(["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"], log, timeout=7200)


def netsh_reset(log: LogFn) -> ActionResult:
    log("네트워크 설정을 초기화합니다.")
    a = _run(["netsh", "int", "ip", "reset"], log)
    b = _run(["netsh", "winsock", "reset"], log)
    log("재부팅 후 적용됩니다.")
    return ActionResult(a.ok and b.ok)


# (filename substring or full stem) -> certutil store name
# Root = 신뢰할 수 있는 루트 인증 기관, CA = 중간 인증 기관
_CERT_STORE_MAP: list[tuple[str, str, str]] = [
    (
        "sectigo_public_code_signing_root_r46",
        "Root",
        "Sectigo Public Code Signing Root R46 → 신뢰할 수 있는 루트 인증 기관",
    ),
    (
        "sectigo_public_code_signing_ca_ev_r36",
        "CA",
        "Sectigo Public Code Signing CA EV R36 → 중간 인증 기관",
    ),
]


def _import_cert_silent(cer: Path, scope: str, store: str, log: LogFn) -> bool:
    """Import via PowerShell — avoids certutil GUI popups."""
    loc = f"Cert:\\{scope}\\{store}"
    ps = (
        f"$p = '{str(cer).replace(chr(39), chr(39)+chr(39))}'; "
        f"Import-Certificate -FilePath $p -CertStoreLocation '{loc}' | Out-Null; "
        "'OK'"
    )
    log(f"인증서 등록: {cer.name} → {scope}\\{store}")
    try:
        from app.winproc import run_silent

        r = run_silent(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps,
            ],
            timeout=30,
        )
        out = _decode_console(r.stdout) + _decode_console(r.stderr)
        if r.returncode == 0 and "OK" in out:
            return True
        # Already present often still returns 0; treat non-zero carefully
        if r.returncode == 0:
            return True
        log(f"  등록 결과: {out.strip()[:200] or f'exit={r.returncode}'}")
        return False
    except Exception as exc:  # noqa: BLE001
        log(f"  오류: {exc}")
        return False


def install_root_certs(log: LogFn) -> ActionResult:
    """Install Sectigo chain to LocalMachine and CurrentUser (Root/CA), no GUI."""
    cert_dir = resource_path("certs")
    ok = True
    found = False
    for stem, store, label in _CERT_STORE_MAP:
        cer = cert_dir / f"{stem}.cer"
        if not cer.exists():
            for ext in (".crt", ".pem"):
                alt = cert_dir / f"{stem}{ext}"
                if alt.exists():
                    cer = alt
                    break
        if not cer.exists():
            log(f"인증서 파일 없음: {stem}.cer")
            ok = False
            continue
        found = True
        log(f"설치: {label}")
        a = _import_cert_silent(cer, "LocalMachine", store, log)
        b = _import_cert_silent(cer, "CurrentUser", store, log)
        ok = ok and (a or b)
    if not found:
        log("설치할 인증서 파일이 없습니다.")
        return ActionResult(False, "no certs")
    return ActionResult(ok)


def collect_support_pack(log: LogFn, *, include_f5_report: bool = True) -> ActionResult:
    """Collect materials engineers need: info, events, reliability, optional F5 HTML."""
    log("지원용 자료를 수집합니다…")
    ensure_work_folder(log)
    results = [
        collect_client_info(log),
        collect_event_logs(log),
        collect_reliability(log),
    ]
    if include_f5_report:
        log("F5 진단 리포트를 수집합니다. 몇 분 걸릴 수 있습니다…")
        results.append(collect_f5_logs(log))
    open_workdir(log)
    ok = all(r.ok for r in results)
    log("자료 수집이 끝났습니다. 작업 폴더를 확인해 주세요.")
    return ActionResult(ok, "support pack")


def open_certmgr(log: LogFn) -> ActionResult:
    log("인증서 관리자를 엽니다.")
    subprocess.Popen(["certmgr.msc"], shell=True)
    return ActionResult(True)


def open_services(log: LogFn) -> ActionResult:
    log("서비스 관리자를 엽니다.")
    subprocess.Popen(["services.msc"], shell=True)
    return ActionResult(True)


def open_internet_options(log: LogFn) -> ActionResult:
    log("인터넷 옵션을 엽니다.")
    subprocess.Popen(["inetcpl.cpl"], shell=True)
    return ActionResult(True)


def disable_crl_check_hint(log: LogFn) -> ActionResult:
    log("인터넷 옵션 > 고급에서 '서버의 인증서 해지 확인' 체크를 해제해 주세요.")
    return open_internet_options(log)


def enable_tls12_hint(log: LogFn) -> ActionResult:
    log("인터넷 옵션 > 고급에서 'TLS 1.2 사용'을 체크해 주세요.")
    return open_internet_options(log)


def open_workdir(log: LogFn) -> ActionResult:
    path = troubleshoot_dir()
    log(f"작업 폴더를 엽니다: {path}")
    os.startfile(path)  # noqa: S606
    return ActionResult(True)


def open_guide_pdf(log: LogFn) -> ActionResult:
    pdf = resource_path("guide", "SW_VPN_User_Issue_Guide_v1.pdf")
    if not pdf.exists():
        log("가이드 파일을 찾을 수 없습니다.")
        return ActionResult(False, "missing")
    log("가이드를 엽니다.")
    os.startfile(pdf)  # noqa: S606
    return ActionResult(True)


def reboot_now(log: LogFn) -> ActionResult:
    log("잠시 후 PC가 다시 시작됩니다.")
    return _run(["shutdown", "/r", "/t", "5"], log)


def check_client_health(log: LogFn) -> ActionResult:
    from app.health import check_edge_client_health

    log("Edge Client 설치 상태를 확인하고 있습니다…")
    result = check_edge_client_health()
    log(f"결과: {result.summary}")
    for reason in result.reasons:
        log(f"  · {reason}")
    for detail in result.details:
        log(f"  - {detail}")
    base = troubleshoot_dir()
    path = base / "health_check.txt"
    lines = [
        f"Summary: {result.summary}",
        f"Healthy: {result.healthy}",
        "",
        "===== Reasons =====",
        *result.reasons,
        "",
        "===== Details =====",
        *result.details,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8-sig")
    log(f"저장 완료: {path}")
    return ActionResult(result.healthy, result.summary)


def collect_event_logs(log: LogFn) -> ActionResult:
    base = troubleshoot_dir() / "EventLogs"
    base.mkdir(parents=True, exist_ok=True)
    log("이벤트 로그를 내보내고 있습니다…")
    ok = True
    for name in ("System", "Application"):
        out = base / f"{name}.evtx"
        r = _run(["wevtutil", "epl", name, str(out)], log)
        ok = ok and r.ok
    log(f"저장 위치: {base}")
    return ActionResult(ok, str(base))


def collect_reliability(log: LogFn) -> ActionResult:
    base = troubleshoot_dir()
    out = base / "reliability.txt"
    log("안정성 기록을 수집하고 있습니다…")
    ps = (
        "Get-WinEvent -LogName 'Microsoft-Windows-ReliabilityAnalysis/Operational' "
        "-MaxEvents 50 -ErrorAction SilentlyContinue | "
        "Format-List TimeCreated, Id, LevelDisplayName, Message | Out-String -Width 200"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        timeout=60,
    )
    text = _decode_console(r.stdout).strip()
    if not text:
        # Fallback: Reliability Monitor summary via Win32_ReliabilityRecords if available
        ps2 = (
            "Get-CimInstance -ClassName Win32_ReliabilityRecords -ErrorAction SilentlyContinue | "
            "Select-Object -First 50 TimeGenerated, EventIdentifier, SourceName, Message | "
            "Format-List | Out-String -Width 200"
        )
        r2 = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps2],
            capture_output=True,
            timeout=60,
        )
        text = _decode_console(r2.stdout).strip() or "(안정성 기록을 가져오지 못했습니다.)"
    out.write_text(text, encoding="utf-8-sig")
    log(f"저장 완료: {out}")
    return ActionResult(True, str(out))


def open_event_viewer(log: LogFn) -> ActionResult:
    log("이벤트 뷰어를 엽니다.")
    subprocess.Popen(["eventvwr.msc"], shell=True)
    return ActionResult(True)


def open_reliability_monitor(log: LogFn) -> ActionResult:
    log("안정성 모니터를 엽니다.")
    subprocess.Popen(["perfmon", "/rel"], shell=False)
    return ActionResult(True)


def analyze_environment(log: LogFn) -> ActionResult:
    """One-shot environment analysis pack for support escalation."""
    log("단말기 환경 분석을 시작합니다…")
    ensure_work_folder(log)
    a = collect_client_info(log)
    b = collect_event_logs(log)
    c = collect_reliability(log)
    d = check_client_health(log)
    # F5 HTML report is slow — collect separately via tools if needed
    log("환경 분석(기본)이 완료되었습니다. F5 로그는 별도로 수집할 수 있습니다.")
    open_workdir(log)
    ok = a.ok and b.ok and c.ok
    return ActionResult(ok, "environment analyzed")


def find_edge_installer() -> Path | None:
    """Look for Edge Client installer under resources/installers."""
    folder = resource_path("installers")
    if not folder.exists():
        return None
    patterns = ("*.msi", "*.exe")
    candidates: list[Path] = []
    for pat in patterns:
        candidates.extend(folder.glob(pat))
    if not candidates:
        return None
    # Prefer names that look like Edge Client
    preferred = [
        p
        for p in candidates
        if any(k in p.name.lower() for k in ("edge", "bigip", "f5", "apm"))
    ]
    pool = preferred or candidates
    return sorted(pool, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def reinstall_edge_client(log: LogFn) -> ActionResult:
    """Delete Edge Client then launch installer if present."""
    log("Edge Client 삭제 후 재설치를 진행합니다…")
    removed = remove_edge_client(log)
    if not removed.ok:
        log("삭제에 실패했습니다. 재설치를 중단합니다.")
        return ActionResult(False, "remove failed")

    installer = find_edge_installer()
    if installer is None:
        log("설치 파일을 찾을 수 없습니다.")
        log("resources/installers 폴더에 Edge Client 설치 파일(.msi/.exe)을 넣어 주세요.")
        log("삭제만 완료되었습니다. 수동으로 재설치해 주세요.")
        return ActionResult(False, "installer missing")

    log(f"설치 파일을 실행합니다: {installer.name}")
    try:
        subprocess.Popen([str(installer)], cwd=str(installer.parent))
    except Exception as exc:  # noqa: BLE001
        log(f"설치 파일 실행 실패: {exc}")
        return ActionResult(False, str(exc))
    log("설치 프로그램이 실행되었습니다. 안내에 따라 설치를 완료해 주세요.")
    return ActionResult(True, str(installer))


# Registry of callable actions for UI / workflows
ACTIONS: dict[str, Callable[[LogFn], ActionResult]] = {
    "ensure_work_folder": ensure_work_folder,
    "collect_client_info": lambda log: collect_client_info(log),
    "collect_f5_logs": collect_f5_logs,
    "remove_edge_client": remove_edge_client,
    "reinstall_edge_client": reinstall_edge_client,
    "open_f5wininfo": open_f5wininfo,
    "list_miniports": list_miniports,
    "remove_miniports": remove_miniports,
    "rescan_devices": rescan_devices,
    "restart_vpn_services": restart_vpn_services,
    "run_sfc": run_sfc,
    "run_dism_scan": run_dism_scan,
    "run_dism_restore": run_dism_restore,
    "netsh_reset": netsh_reset,
    "install_root_certs": install_root_certs,
    "open_certmgr": open_certmgr,
    "open_services": open_services,
    "open_internet_options": open_internet_options,
    "disable_crl_check_hint": disable_crl_check_hint,
    "enable_tls12_hint": enable_tls12_hint,
    "open_workdir": open_workdir,
    "open_guide_pdf": open_guide_pdf,
    "reboot_now": reboot_now,
    "check_client_health": check_client_health,
    "collect_event_logs": collect_event_logs,
    "collect_reliability": collect_reliability,
    "open_event_viewer": open_event_viewer,
    "open_reliability_monitor": open_reliability_monitor,
    "analyze_environment": analyze_environment,
    "collect_support_pack": lambda log: collect_support_pack(log, include_f5_report=True),
}
