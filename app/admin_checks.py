"""Admin-mode selectable diagnostic / remediation items."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdminItem:
    id: str
    title: str
    group: str
    kind: str  # diagnose | action
    target: str
    destructive: bool = False


ADMIN_ITEMS: list[AdminItem] = [
    AdminItem("a_install", "설치 상태 및 버전 확인", "Edge Client", "diagnose", "install_presence"),
    AdminItem("a_comp", "필수 구성 요소 파일", "Edge Client", "diagnose", "component_files"),
    AdminItem("a_svc", "F5 서비스 점검", "Edge Client", "diagnose", "f5_services"),
    AdminItem("a_sig", "설치 파일 디지털 서명", "Edge Client", "diagnose", "installer_signature"),
    AdminItem("a_cert", "Sectigo 코드 서명 인증서 체인", "Edge Client", "diagnose", "cert_sectigo_chain"),
    AdminItem("a_log", "환경 정보 수집", "Edge Client", "action", "collect_client_info"),
    AdminItem("a_dns", "공인 DNS 조회", "네트워크", "diagnose", "dns_public"),
    AdminItem("a_vpn_dns", "VPN FQDN DNS", "네트워크", "diagnose", "dns_vpn"),
    AdminItem("a_tls", "VPN HTTPS/TLS", "네트워크", "diagnose", "https_vpn"),
    AdminItem("a_proxy", "프록시 설정", "네트워크", "diagnose", "proxy_settings"),
    AdminItem("a_route", "기본 라우팅", "네트워크", "diagnose", "routing_default"),
    AdminItem("a_adapter", "VPN 가상 어댑터", "네트워크", "diagnose", "vpn_adapter"),
    AdminItem("a_osvpn", "Windows VPN 지원 서비스", "VPN 및 보안", "diagnose", "os_vpn_services"),
    AdminItem("a_auth", "인증 실패 안내(관리자)", "VPN 및 보안", "diagnose", "auth_failure_hint"),
    AdminItem("a_evt", "이벤트 로그 수집", "VPN 및 보안", "action", "collect_event_logs"),
    AdminItem("a_report", "F5 HTML 진단 보고서", "진단 및 복구", "action", "collect_f5_logs"),
    AdminItem("a_pack", "진단 로그 일괄 수집", "진단 및 복구", "action", "analyze_environment"),
    AdminItem("a_cert_install", "Sectigo 인증서 설치", "진단 및 복구", "action", "install_root_certs"),
    AdminItem("a_recheck", "설치 헬스 재점검", "진단 및 복구", "action", "check_client_health"),
]

ADMIN_GROUPS = ["Edge Client", "네트워크", "VPN 및 보안", "진단 및 복구"]
