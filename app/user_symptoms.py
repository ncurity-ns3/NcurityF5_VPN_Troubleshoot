"""End-user symptom menu (8 items) — guide-aligned classification."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Symptom:
    id: str
    title: str
    hint: str = ""
    check_ids: tuple[str, ...] = field(default_factory=tuple)


SYMPTOMS: list[Symptom] = [
    Symptom(
        id="install_fail",
        title="VPN 프로그램 설치가 안 돼요",
        hint="설치 실패, 설치 롤백, 업데이트 오류",
        check_ids=(
            "install_presence",
            "component_files",
            "installer_signature",
            "cert_sectigo_chain",
            "windows_installer",
            "leftover_install",
            "admin_elevation",
        ),
    ),
    Symptom(
        id="not_running",
        title="VPN 프로그램이 실행되지 않아요",
        hint="실행 불가, 실행 직후 종료 (연결 후 '초기화 중'은 여기 해당 없음)",
        check_ids=(
            "install_presence",
            "client_binary",
            "component_files",
            "f5_services",
            "vpn_adapter",
        ),
    ),
    Symptom(
        id="stuck_initializing",
        title="VPN 연결 시 '초기화 중'에서 멈춰요",
        hint="연결 시도 이후 터널 초기화 멈춤 (프로그램 실행 직후와 구분)",
        check_ids=(
            "tunnel_init_hint",
            "f5_services",
            "os_vpn_services",
            "wan_miniport_hint",
            "vpn_adapter",
            "component_files",
            "bigip_possible_hint",
        ),
    ),
    Symptom(
        id="connect_error_msg",
        title="VPN 연결 시 오류 메시지가 나타나요",
        hint="서버 연결 불가, 연결 장치 오류, 인증서 해지 오류 등",
        check_ids=(
            "error_message_hint",
            "vpn_fqdn_config",
            "dns_vpn",
            "https_vpn",
            "proxy_settings",
            "component_files",
            "os_vpn_services",
            "vpn_adapter",
            "auth_failure_hint",
        ),
    ),
    Symptom(
        id="no_internet_after",
        title="VPN 연결 후 인터넷이 안 돼요",
        hint="외부 웹 접속 불가 (정책·터널 방식에 따라 정상일 수 있음)",
        check_ids=(
            "vpn_adapter",
            "routing_default",
            "dns_public",
            "proxy_settings",
            "internet_basic",
            "tunnel_policy_hint",
        ),
    ),
    Symptom(
        id="no_internal",
        title="VPN 연결 후 회사 시스템에 접속이 안 돼요",
        hint="업무 사이트·내부 서버 접속 실패",
        check_ids=(
            "vpn_adapter",
            "internal_target_config",
            "dns_internal",
            "https_internal",
            "proxy_settings",
            "acl_admin_hint",
        ),
    ),
    Symptom(
        id="disconnects",
        title="VPN 연결이 자꾸 끊겨요",
        hint="연결 직후 또는 사용 중 종료",
        check_ids=(
            "internet_basic",
            "f5_services",
            "vpn_adapter",
            "proxy_settings",
            "security_soft_hint",
            "session_admin_hint",
        ),
    ),
    Symptom(
        id="slow",
        title="VPN 연결 후 속도가 느려요",
        hint="웹·업무 시스템 응답 지연 (구간별 시간 측정)",
        check_ids=(
            "latency_dns",
            "latency_https",
            "proxy_settings",
            "routing_default",
            "vpn_adapter",
        ),
    ),
]

FULL_SCAN = Symptom(
    id="full_scan",
    title="전체 점검하기",
    hint="무엇이 문제인지 모르겠다면 선택하세요. 실행 가능한 항목만 점검합니다.",
    check_ids=tuple(dict.fromkeys(cid for s in SYMPTOMS for cid in s.check_ids)),
)


def get_symptom(symptom_id: str) -> Symptom | None:
    if symptom_id == FULL_SCAN.id:
        return FULL_SCAN
    for s in SYMPTOMS:
        if s.id == symptom_id:
            return s
    return None
