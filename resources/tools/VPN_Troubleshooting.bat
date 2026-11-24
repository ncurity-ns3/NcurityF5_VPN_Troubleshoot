@echo off
chcp 949 > nul
REM UTF-8 with BOM으로 설정할 것.
setlocal enabledelayedexpansion

REM =========================================================
REM  Ncurity Troubleshooting Program v4.4.0 (26.01.30)
REM  - F5 SSL VPN 이슈 자동 점검 스크립트
REM
REM  Versioning Guide
REM    Major   : X      큰 규격/동작 변경
REM    Minor   : .Y     점검 항목/기능 추가
REM    Engineer: .Z     버그 수정 / 동작 안정화
REM =========================================================

REM ------------------------------
REM 공통 경로/파일 설정
REM ------------------------------
set "TS_DIR=%USERPROFILE%\Desktop\F5_VPN_Troubleshoot"
set "CLIENTINFO=%TS_DIR%\%USERNAME%_ClientInfo.txt"
set "LOGFILE=%TS_DIR%\f5win_troubleshoot_result.txt"

REM ------------------------------
REM WAN Miniport Instance ID 목록
REM ------------------------------
set "MP_IP=SWD\MSRRAS\MS_NDISWANIP"
set "MP_IPV6=SWD\MSRRAS\MS_NDISWANIPV6"
set "MP_L2TP=SWD\MSRRAS\MS_L2TPMINIPORT"
set "MP_PPPOE=SWD\MSRRAS\MS_PPPOEMINIPORT"
set "MP_PPTP=SWD\MSRRAS\MS_PPTPMINIPORT"
set "MP_SSTP=SWD\MSRRAS\MS_SSTPMINIPORT"
set "MP_IKEV2=SWD\MSRRAS\MS_AGILEVPNMINIPORT"
set "MP_MONITOR=SWD\MSRRAS\MS_NDISWANBH"

REM =========================================================
REM [Step 0] 관리자 권한 확인
REM =========================================================
net session >nul 2>&1
if '%errorlevel%' NEQ '0' (
    echo [Step 0] 관리자 권한 확인 ... [FAIL]
    echo 관리자 권한이 필요합니다. 관리자 권한으로 다시 실행합니다.
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\uac_get_admin.vbs"
    set params = %*:"=""
    echo UAC.ShellExecute "cmd.exe", "/c %~s0 %params%", "", "runas", 1 >> "%temp%\uac_get_admin.vbs"
    "%temp%\uac_get_admin.vbs"
    del "%temp%\uac_get_admin.vbs"
    exit /b
) else (
    echo [Step 0] 관리자 권한 확인 ... [OK]
)

REM =========================================================
REM  실행 여부 확인
REM =========================================================
set /p startcheck=F5 SSL VPN 이슈 분석을 실행 하시겠습니까? [Y/N]:
if /i "%startcheck%"=="Y" (
    echo.
    echo F5 SSL VPN 이슈 분석을 진행합니다.
    timeout 3 >nul
) else (
    echo.
    echo F5 SSL VPN 이슈 분석을 종료합니다.
    goto :Closed
)

REM =========================================================
REM [Step 1] 작업 폴더/버전 정보 수집
REM =========================================================
echo.
echo [Step 1] 작업 폴더 및 Windows Version을 확인 중입니다...

if not exist "%TS_DIR%\" (
    echo 바탕화면에 F5_VPN_Troubleshoot 폴더를 생성합니다...
    mkdir "%TS_DIR%"
    timeout 2 >nul
)

REM Windows 버전 정보 기록 (새 파일 생성/초기화)
ver > "%CLIENTINFO%"
echo Date/Time : %DATE% %TIME%>>"%CLIENTINFO%"
echo ---------------------------------------->>"%CLIENTINFO%"

echo Windows Version 확인 및 ClientInfo 초기화 완료.
timeout 2 >nul

REM =========================================================
REM [Step 2] 설치 정보 확인(폴더 존재 재확인)
REM =========================================================
echo.
echo [Step 2] F5 SSL VPN 설치 정보를 체크합니다...

if not exist "%TS_DIR%\" (
    echo 바탕화면에 F5_VPN_Troubleshoot 폴더를 생성합니다...
    mkdir "%TS_DIR%"
    timeout 2 >nul
)

echo 폴더 확인 완료.
timeout 1 >nul

REM =========================================================
REM [Step 3] 사용자 환경 정보 입력
REM =========================================================
:ClientInfo
echo.
echo [Step 3] 사용자 환경 정보를 입력합니다.

set /p "OSInfo=OS Version을 입력하세요 [예: Windows 10 22H2, MacOS Sonoma]: "

echo.>>"%CLIENTINFO%"
echo ===== Client Environment =====>>"%CLIENTINFO%"
echo OS Version (사용자 입력) : %OSInfo%>>"%CLIENTINFO%"
echo.>>"%CLIENTINFO%"

echo 사용자 환경 정보가 ClientInfo 파일에 저장되었습니다.
timeout 2 >nul

REM =========================================================
REM [Step 4] 로그 파일 설정 및 안내 메시지
REM =========================================================
echo.
echo [Step 4] VPN 연결을 위한 사전 안내를 출력합니다.

call :log [Step 4] VPN 연결을 위한 설정을 시작합니다.
call :log [Step 4] 반드시 모든 브라우저 창을 모두 종료한 후 진행해 주십시오.

REM =========================================================
REM [Step 5] f5wininfo 실행 및 Edge Client 삭제 확인
REM =========================================================
call :log [Step 5] f5wininfo 실행 중...
cd /d "%~dp0"

REM f5wininfo.exe 존재 여부 확인
if not exist "f5wininfo.exe" (
    call :log [Step 5] f5wininfo.exe not found ... [FAIL]
    goto :AfterF5Wininfo
)

REM f5wininfo 실행 (Edge Client 제거 포함)
start "" /b f5wininfo.exe /r
call :log [Step 5] f5wininfo 실행됨... Edge Client 삭제 중
echo ※ Edge Client 삭제는 PC 성능에 따라 시간이 오래 걸릴 수 있습니다.

REM Edge Client 삭제 완료될 때까지 대기
set "sec=0"
:F5Wait
if not exist "C:\Program Files (x86)\F5 Networks\Edge Client" (
    call :log [Step 5] Edge Client 삭제 완료 ... [OK]
    goto :AfterF5Wininfo
)

set /a sec+=1
call :log [Step 5] Edge Client 삭제 진행 중... (!sec!초 경과)
choice /C Y /N /D Y /T 1 >nul
goto :F5Wait

:AfterF5Wininfo

REM =========================================================
REM [Step 6] Miniport 어댑터 제거
REM =========================================================
call :log [Step 6] Miniport 어댑터 제거 중...

call :log [Step 6] 제거 전 WAN Miniport 상태 확인
powershell -NoProfile -Command "Get-PnpDevice -Class Net | Where-Object {$_.InstanceId -in @('%MP_IP%','%MP_IPV6%','%MP_L2TP%','%MP_PPPOE%','%MP_PPTP%','%MP_SSTP%','%MP_IKEV2%','%MP_MONITOR%')} | Select-Object Status,FriendlyName,InstanceId | Format-Table -AutoSize | Out-String | Tee-Object -FilePath '%LOGFILE%' -Append"

call :log [Step 6] WAN Miniport 제거 시작
pnputil /remove-device "%MP_IP%"      2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"
pnputil /remove-device "%MP_IPV6%"    2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"
pnputil /remove-device "%MP_L2TP%"    2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"
pnputil /remove-device "%MP_PPPOE%"   2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"
pnputil /remove-device "%MP_PPTP%"    2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"
pnputil /remove-device "%MP_SSTP%"    2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"
pnputil /remove-device "%MP_IKEV2%"   2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"
pnputil /remove-device "%MP_MONITOR%" 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"

call :log [Step 6] 제거 후 WAN Miniport 상태 확인
powershell -NoProfile -Command "Get-PnpDevice -Class Net | Where-Object {$_.InstanceId -in @('%MP_IP%','%MP_IPV6%','%MP_L2TP%','%MP_PPPOE%','%MP_PPTP%','%MP_SSTP%','%MP_IKEV2%','%MP_MONITOR%')} | Select-Object Status,FriendlyName,InstanceId | Format-Table -AutoSize | Out-String | Tee-Object -FilePath '%LOGFILE%' -Append"

call :log [Step 6] Miniport 어댑터 제거 완료 ... [OK]

REM =========================================================
REM [Step 7] Miniport 어댑터 초기화
REM =========================================================
call :log [Step 7] 하드웨어 변경 사항 검색(초기화) 시작
pnputil /scan-devices 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"

REM 장치가 다시 올라올 시간 대기
timeout /t 5 >nul

call :log [Step 7] 초기화 후 WAN Miniport 최종 상태 확인
powershell -NoProfile -Command "Get-PnpDevice -Class Net | Where-Object {$_.InstanceId -in @('%MP_IP%','%MP_IPV6%','%MP_L2TP%','%MP_PPPOE%','%MP_PPTP%','%MP_SSTP%','%MP_IKEV2%','%MP_MONITOR%')} | Select-Object Status,FriendlyName,InstanceId | Format-Table -AutoSize | Out-String | Tee-Object -FilePath '%LOGFILE%' -Append"

call :log [Step 7] Miniport 어댑터 초기화 완료 ... [OK]

REM =========================================================
REM [Step 8] VPN 관련 서비스 재시작
REM =========================================================
set "result=OK"
call :log [Step 8] VPN 관련 서비스 재시작 중...

REM STOP 순서: RasMan → TapiSrv → SstpSvc
call :log [Step 8] 서비스 중지 순서: RasMan → TapiSrv → SstpSvc
call :svc RasMan stop STOPPED
call :svc TapiSrv stop STOPPED
call :svc SstpSvc stop STOPPED

REM START 순서: RasMan → TapiSrv → SstpSvc
call :log [Step 8] 서비스 시작 순서: RasMan → TapiSrv → SstpSvc
call :svc RasMan start RUNNING
call :svc TapiSrv start RUNNING
call :svc SstpSvc start RUNNING

call :log [Step 8] VPN 관련 서비스 재시작 완료
call :log [Step 8] 서비스 재시작 전체 결과: %result%

REM =========================================================
REM [Step 9] 시스템 파일 검사 (SFC)
REM =========================================================
call :log [Step 9] 시스템 파일 검사(SFC) 시작 (진행률이 화면에 실시간으로 표시됩니다)
sfc /scannow
call :log [Step 9] 시스템 파일 검사(SFC) 완료 (종료 코드: %ERRORLEVEL%)

REM sfc는 화면-갱신 방식(캐리지리턴) 특성상 파이프로 실시간 캡처가 불가능하여
REM 완료 후 CBS.log에서 관련 항목(최근 100줄)만 별도로 추출해 로그파일에 남깁니다.
echo. >> "%LOGFILE%"
echo ===== SFC 상세 내역 (CBS.log [SR] 최근 100줄) ===== >> "%LOGFILE%"
powershell -NoProfile -Command "if (Test-Path '%windir%\Logs\CBS\CBS.log') { Select-String -Path '%windir%\Logs\CBS\CBS.log' -Pattern '\[SR\]' -Encoding UTF8 | Select-Object -Last 100 | ForEach-Object { $_.Line } | Out-File -FilePath '%LOGFILE%' -Append -Encoding utf8 }"

REM =========================================================
REM [Step 10] 이미지 상태 점검 및 복구 (DISM)
REM =========================================================
call :log [Step 10] Windows 이미지 상태 점검(DISM /ScanHealth) 시작
DISM /Online /Cleanup-Image /ScanHealth >>"%LOGFILE%"
call :log [Step 10] Windows 이미지 손상 검사 완료

call :log [Step 10] Windows 이미지 복구 시도(DISM /RestoreHealth) 시작
DISM /Online /Cleanup-Image /RestoreHealth >>"%LOGFILE%"
if %ERRORLEVEL% EQU 0 (
    call :log [Step 10] Windows 이미지 복구 성공
) else (
    call :log [Step 10] Windows 이미지 복구 실패 - 설치 미디어가 필요할 수 있습니다.
)

timeout 5 >nul
echo.
echo 이슈 원인 분석에 필요한 자료를 모두 추출했습니다.
echo 바탕화면의 [F5_VPN_Troubleshoot] 폴더와 오류 메시지를 공유해 주세요.
echo.

REM =========================================================
REM [Step 11] 재부팅 여부 확인
REM =========================================================
call :log [Step 11] 재부팅 여부 확인
echo 재부팅 후 SSL VPN Client Program을 재설치해 주십시오.
echo 작업이 완료되었습니다. 재부팅 하시겠습니까? (Y/N)
set /p rebootChoice=

if /i "%rebootChoice%"=="Y" (
    call :log [Step 11] 사용자 선택: 재부팅 진행
    shutdown /r
) else (
    call :log [Step 11] 사용자 선택: 재부팅 생략
    echo 수동으로 재부팅 후 VPN을 다시 실행해 주세요.
)

REM =========================================================
REM 종료 메시지
REM =========================================================
call :log 로그 파일이 바탕화면에 저장되었습니다: %LOGFILE%
echo 로그 파일이 바탕화면에 저장되었습니다: %LOGFILE%

goto :Closed

:Closed
endlocal
exit /b

REM =========================================================
REM [공통 함수] 콘솔 + 로그 동시 출력
REM =========================================================
:log
echo %*
echo %*>>"%LOGFILE%"
goto :eof

REM =========================================================
REM [공통 함수] 서비스 제어 (start/stop + 상태 확인)
REM    인자:
REM      %1 = 서비스 이름 (예: RasMan)
REM      %2 = start | stop
REM      %3 = 기대 상태 (RUNNING | STOPPED)
REM =========================================================
:svc
set "_svcname=%~1"
set "_svcaction=%~2"
set "_svcgoal=%~3"

call :log %_svcaction%ing %_svcname%...

if /i "%_svcaction%"=="start" (
    echo.| sc start "%_svcname%" >nul
) else (
    sc stop "%_svcname%" >nul
)

:svc_wait
sc query "%_svcname%" | find "%_svcgoal%" >nul
if %errorlevel%==0 (
    call :log [OK] %_svcname% %_svcgoal%
    exit /b
)

timeout /t 1 >nul
goto :svc_wait