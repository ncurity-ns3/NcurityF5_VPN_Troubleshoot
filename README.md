# F5 SSL VPN Troubleshoot Tool

F5 BIG-IP Edge Client SSL VPN 이슈를 **증상 선택 → 자동 점검 → 해결/관리자 안내**로 다루는 Windows 도구입니다.  
기존 `VPN_Troubleshooting.bat` 일괄 실행을 GUI로 분리했고, `(엔큐리티) SW VPN 사용자이슈 가이드_v1`을 반영했습니다.

디자인(사이드바 + 카드 + 블루 액센트)은 [NcurityF5_Tool](https://github.com/ncurity-ns3/NcurityF5_Tool)과 동일한 토큰을 사용합니다.  
고객 전달을 고려해 **브랜드 로고는 UI에 표시하지 않습니다.**

현재 버전: **1.4.1** — 변경 이력은 [CHANGELOG.md](CHANGELOG.md), 릴리즈 노트는 [docs/releases](docs/releases) 를 참고하세요.

## 실행

관리자 권한이 필요합니다. 콘솔 창 없이 실행하려면:

```bat
run.bat
```

또는:

```bat
pythonw main.pyw
```

개발 중 로그가 필요하면 `python main.py` 를 사용하세요 (콘솔가 잠시 보일 수 있으나 앱에서 숨깁니다).

## 구성

| 영역 | 설명 |
|------|------|
| 홈 | 설치 상태 확인(수동) · 환경 분석 |
| 이슈별 조치 | 전체 점검 + 증상 8개 자동 진단 (PC/관리자/보류 구분) |
| 개별 도구 | 환경 분석 · 임시 조치 · 삭제/재설치 |
| 관리자 진단 | 체크리스트 선택 점검 |
| 가이드 | PDF 요약 + 열기 |

`resources/config.json` 에 `vpn_fqdn`, `internal_test_hosts` 등을 넣으면 서버·내부 접속 진단이 정확해집니다.

번들 리소스:

- `resources/tools/f5wininfo.exe` — Edge Client 삭제(`/r`)에 필요
- `resources/guide/SW_VPN_User_Issue_Guide_v1.pdf`
- `resources/certs/sectigo_*.cer` — Sectigo Code Signing Root R46 / CA EV R36
- `resources/branding/` — Ncurity 로고/아이콘
- `resources/installers/` — 「삭제 후 재설치」용 Edge Client 설치 파일 (선택)

결과는 바탕화면 `F5_VPN_Troubleshoot` 폴더에 저장됩니다.

## 예: 「초기화 중」

1. WAN Miniport 삭제  
2. Miniport 재검색/재설치  
3. VPN 서비스 재시작  
4. Edge Client 삭제 (`f5wininfo /r`)  
5. (선택) SFC  
6. 재부팅 → Edge Client 재설치  

각 단계는 **실행** 버튼으로 개별 수행하거나, **남은 단계 순서대로 실행**으로 일괄 수행할 수 있습니다.

## PyInstaller (선택)

```bat
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Ncurity_VPN_Troubleshoot" ^
  --icon resources\branding\ncurity_app_icon.ico ^
  --add-data "resources;resources" ^
  main.py
```
