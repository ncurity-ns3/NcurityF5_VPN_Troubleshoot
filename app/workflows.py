"""Issue-based workflows — customer-facing copy."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    action_id: str
    title: str
    description: str = ""
    destructive: bool = False
    requires_confirm: bool = False


@dataclass
class IssueWorkflow:
    id: str
    title: str
    summary: str
    guide_ref: str
    steps: list[Step] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ToolSection:
    title: str
    summary: str
    steps: list[Step] = field(default_factory=list)


TOOL_SECTIONS: list[ToolSection] = [
    ToolSection(
        title="환경 분석",
        summary="지원 요청에 필요한 단말기 정보를 한 번에 모읍니다.",
        steps=[
            Step(
                "analyze_environment",
                "단말기 환경 분석",
                "환경 정보 · 이벤트 로그 · 안정성 · 헬스 체크를 수집합니다",
            ),
            Step("collect_client_info", "환경 정보 수집", "OS, IP, 라우팅 정보를 저장합니다"),
            Step("collect_f5_logs", "F5 로그 수집", "진단 리포트 생성 (수 분 소요)"),
            Step("collect_event_logs", "이벤트 로그 내보내기", "System/Application .evtx"),
            Step("collect_reliability", "안정성 기록 수집"),
            Step("check_client_health", "설치 상태 다시 확인"),
            Step("open_event_viewer", "이벤트 뷰어 열기"),
            Step("open_reliability_monitor", "안정성 모니터 열기"),
            Step("open_workdir", "작업 폴더 열기"),
        ],
    ),
    ToolSection(
        title="임시 조치",
        summary="재설치 전에 시도할 수 있는 빠른 조치입니다.",
        steps=[
            Step("list_miniports", "WAN Miniport 상태 확인"),
            Step(
                "remove_miniports",
                "WAN Miniport 삭제",
                "VPN용 네트워크 어댑터를 제거합니다",
                destructive=True,
                requires_confirm=True,
            ),
            Step("rescan_devices", "Miniport 재설치", "네트워크 어댑터를 다시 인식합니다"),
            Step("restart_vpn_services", "VPN 서비스 재시작"),
            Step("run_sfc", "시스템 파일 검사", "완료까지 시간이 걸릴 수 있습니다"),
            Step("run_dism_scan", "Windows 이미지 검사"),
            Step("run_dism_restore", "Windows 이미지 복구", "완료까지 시간이 걸릴 수 있습니다"),
            Step(
                "netsh_reset",
                "네트워크 초기화",
                "적용을 위해 재부팅이 필요합니다",
                destructive=True,
                requires_confirm=True,
            ),
            Step(
                "install_root_certs",
                "Sectigo 인증서 설치",
                "Root R46 → 루트 / CA EV R36 → 중간 인증 기관",
            ),
            Step("open_certmgr", "인증서 관리자 열기"),
            Step("open_services", "서비스 관리자 열기"),
            Step("open_internet_options", "인터넷 옵션 열기"),
        ],
    ),
    ToolSection(
        title="삭제 / 재설치",
        summary="Edge Client를 제거하거나, 삭제 후 설치 파일을 실행합니다.",
        steps=[
            Step(
                "remove_edge_client",
                "Edge Client 삭제",
                "재설치 전에 프로그램을 제거합니다",
                destructive=True,
                requires_confirm=True,
            ),
            Step(
                "reinstall_edge_client",
                "삭제 후 재설치",
                "삭제 후 resources/installers 의 설치 파일을 실행합니다",
                destructive=True,
                requires_confirm=True,
            ),
            Step(
                "reboot_now",
                "지금 재부팅",
                "잠시 후 PC가 다시 시작됩니다",
                destructive=True,
                requires_confirm=True,
            ),
        ],
    ),
    ToolSection(
        title="기타",
        summary="작업 폴더·진단 도구·가이드",
        steps=[
            Step("ensure_work_folder", "작업 폴더 생성", "바탕화면에 결과 저장 폴더를 만듭니다"),
            Step("open_f5wininfo", "f5wininfo 실행", "진단 도구를 엽니다"),
            Step("open_guide_pdf", "이용 가이드 열기"),
        ],
    ),
]

# Flat list kept for any callers that still expect it
INDIVIDUAL_TOOLS: list[Step] = [s for sec in TOOL_SECTIONS for s in sec.steps]


ISSUES: list[IssueWorkflow] = [
    IssueWorkflow(
        id="initializing",
        title="초기화 중",
        summary="VPN 연결에 필요한 구성 요소가 정상적이지 않을 때 나타날 수 있습니다.",
        guide_ref="초기화 중",
        notes=[
            "진행 전에 브라우저를 모두 종료해 주세요.",
            "Miniport 재설치 → 서비스 재시작 → Edge Client 재설치 → 재부팅 순서를 권장합니다.",
            "시스템 파일 검사는 시간이 오래 걸릴 수 있습니다.",
        ],
        steps=[
            Step("ensure_work_folder", "1. 작업 폴더 준비"),
            Step(
                "remove_miniports",
                "2. WAN Miniport 삭제",
                destructive=True,
                requires_confirm=True,
            ),
            Step("rescan_devices", "3. Miniport 재설치"),
            Step("restart_vpn_services", "4. VPN 서비스 재시작"),
            Step(
                "remove_edge_client",
                "5. Edge Client 삭제",
                "삭제 후 재부팅하고 Edge Client를 다시 설치하세요",
                destructive=True,
                requires_confirm=True,
            ),
            Step("run_sfc", "6. 시스템 파일 검사 (선택)"),
            Step(
                "reboot_now",
                "7. 재부팅",
                "재부팅 후 Edge Client를 다시 설치하세요",
                destructive=True,
                requires_confirm=True,
            ),
        ],
    ),
    IssueWorkflow(
        id="install_fail",
        title="Edge Client 설치 실패",
        summary="인증서가 없거나 보안 프로그램과 충돌하면 설치가 실패할 수 있습니다.",
        guide_ref="설치 실패",
        notes=[
            "인증서 관리자에서 Sectigo Public Code Signing Root R46(루트) · CA EV R36(중간) 설치 여부를 확인해 주세요.",
            "설치가 롤백되거나 VPN 연결 후 인터넷이 안 되면, 삭제 후 재부팅하고 보안 프로그램을 잠시 중지한 뒤 다시 설치해 보세요.",
        ],
        steps=[
            Step("open_certmgr", "1. 인증서 확인"),
            Step("install_root_certs", "2. Sectigo 인증서 설치"),
            Step(
                "remove_edge_client",
                "3. Edge Client 삭제",
                destructive=True,
                requires_confirm=True,
            ),
            Step(
                "reboot_now",
                "4. 재부팅",
                "재부팅 후 Edge Client를 다시 설치하세요",
                destructive=True,
                requires_confirm=True,
            ),
        ],
    ),
    IssueWorkflow(
        id="crl_error",
        title="해지 서버에 연결할 수 없거나 확정 응답을 받을 수 없습니다",
        summary="인증서 해지 확인 과정에서 오류가 발생할 수 있습니다.",
        guide_ref="해지 서버 오류",
        notes=[
            "인터넷 옵션 > 고급에서 '서버의 인증서 해지 확인' 체크를 해제해 주세요.",
        ],
        steps=[
            Step("disable_crl_check_hint", "1. 인터넷 옵션 열기"),
        ],
    ),
    IssueWorkflow(
        id="no_device",
        title="네트워크 접속 연결 장치를 찾을 수 없습니다",
        summary="VPN 프로그램이 제대로 설치되지 않았거나 관련 서비스가 중지된 경우입니다.",
        guide_ref="연결 장치 없음",
        notes=[
            "f5wininfo에서 구성 요소 제거 후 재설치가 필요할 수 있습니다.",
            "서비스 관리자에서 Remote Access Connection Manager, Secure Socket Tunneling Protocol, Telephony가 시작 상태인지 확인해 주세요.",
        ],
        steps=[
            Step("open_f5wininfo", "1. f5wininfo 실행"),
            Step("restart_vpn_services", "2. VPN 서비스 재시작"),
            Step("open_services", "3. 서비스 상태 확인"),
            Step(
                "remove_edge_client",
                "4. Edge Client 삭제 (필요 시)",
                destructive=True,
                requires_confirm=True,
            ),
        ],
    ),
    IssueWorkflow(
        id="no_internet_after_vpn",
        title="VPN 연결 후 인터넷 접속 불가",
        summary="Windows 버전 문제이거나, PC IP가 공인 대역이라 터널 라우팅이 막히는 경우일 수 있습니다.",
        guide_ref="인터넷 접속 불가",
        notes=[
            "Windows를 최신 버전으로 업데이트해 주세요.",
            "연결된 네트워크 IP가 공인 대역이면 사설 IP로 변경이 필요할 수 있습니다.",
            "아래 정보를 수집해 담당자에게 전달해 주세요.",
        ],
        steps=[
            Step("collect_client_info", "1. 환경 정보 수집"),
            Step("collect_f5_logs", "2. F5 로그 수집"),
            Step("open_workdir", "3. 작업 폴더 열기"),
        ],
    ),
    IssueWorkflow(
        id="no_tunnel",
        title="VPN 터널이 생기지 않음",
        summary="네트워크 구성이 손상되어 VPN 터널이 만들어지지 않을 수 있습니다.",
        guide_ref="터널 미생성",
        notes=[
            "시스템 검사 후 네트워크를 초기화합니다.",
            "네트워크 초기화 후에는 반드시 재부팅해 주세요.",
        ],
        steps=[
            Step("run_sfc", "1. 시스템 파일 검사"),
            Step("run_dism_scan", "2. Windows 이미지 검사"),
            Step("run_dism_restore", "3. Windows 이미지 복구"),
            Step(
                "netsh_reset",
                "4. 네트워크 초기화",
                destructive=True,
                requires_confirm=True,
            ),
            Step(
                "reboot_now",
                "5. 재부팅",
                destructive=True,
                requires_confirm=True,
            ),
        ],
    ),
    IssueWorkflow(
        id="cannot_connect_server",
        title="서버에 연결할 수 없습니다",
        summary="TLS 1.2가 꺼져 있으면 서버와 연결되지 않을 수 있습니다.",
        guide_ref="서버 연결 실패",
        notes=["인터넷 옵션 > 고급에서 'TLS 1.2 사용'을 체크해 주세요."],
        steps=[
            Step("enable_tls12_hint", "1. 인터넷 옵션 열기"),
        ],
    ),
    IssueWorkflow(
        id="full_bat",
        title="전체 점검",
        summary="주요 점검·조치를 순서대로 진행합니다. 단계별 또는 한 번에 실행할 수 있습니다.",
        guide_ref="전체 점검",
        notes=[
            "진행 전에 브라우저를 모두 종료해 주세요.",
            "완료 후 바탕화면의 F5_VPN_Troubleshoot 폴더를 담당자에게 전달해 주세요.",
        ],
        steps=[
            Step("ensure_work_folder", "1. 작업 폴더 준비"),
            Step("collect_client_info", "2. 환경 정보 수집"),
            Step(
                "remove_edge_client",
                "3. Edge Client 삭제",
                destructive=True,
                requires_confirm=True,
            ),
            Step(
                "remove_miniports",
                "4. WAN Miniport 삭제",
                destructive=True,
                requires_confirm=True,
            ),
            Step("rescan_devices", "5. Miniport 재설치"),
            Step("restart_vpn_services", "6. VPN 서비스 재시작"),
            Step("run_sfc", "7. 시스템 파일 검사"),
            Step("run_dism_scan", "8. Windows 이미지 검사"),
            Step("run_dism_restore", "9. Windows 이미지 복구"),
            Step(
                "reboot_now",
                "10. 재부팅",
                "재부팅 후 Edge Client를 다시 설치하세요",
                destructive=True,
                requires_confirm=True,
            ),
        ],
    ),
]


def get_issue(issue_id: str) -> IssueWorkflow | None:
    for issue in ISSUES:
        if issue.id == issue_id:
            return issue
    return None
