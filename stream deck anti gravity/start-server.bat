@echo off
title AntiGravity Stream Deck Server V2
color 0A
echo.
echo  ========================================================
echo   ___        _   _ _____               _ _
echo  / _ \      | | (_)  __ \             (_) |
echo / /_\ \_ __ | |_ _| |  \/_ __ __ ___   _| |_ _   _
echo |  _  | '_ \| __| | | __| '__/ _` \ \ / / __| | | |
echo | | | | | | | |_| | |_\ \ | | (_| |\ V /| |_| |_| |
echo \_| |_/_| |_|\__|_|\____/_|  \__,_| \_/  \__|\__, |
echo                                                __/ |
echo                             Stream Deck V2    |___/
echo  ========================================================
echo.
echo  [*] Verificando Node.js...

where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  [ERRO] Node.js nao encontrado! Instale em: https://nodejs.org
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
echo  [OK] Node.js %NODE_VER% encontrado.

if not exist "%~dp0server-windows\dist\index.js" (
    echo.
    echo  [*] Build nao encontrado. Compilando TypeScript...
    cd /d "%~dp0server-windows"
    call npm run build
    if %ERRORLEVEL% neq 0 (
        echo  [ERRO] Falha na compilacao! Verifique os erros acima.
        pause
        exit /b 1
    )
    echo  [OK] Build concluido com sucesso!
)

echo.
echo  [*] Iniciando servidor AntiGravity Stream Deck...
echo.
echo  --------------------------------------------------------
echo   Dashboard:  http://localhost:5000
echo   WebSocket:  ws://localhost:5001
echo   API Info:   http://localhost:5000/api/info
echo  --------------------------------------------------------
echo.
echo  Conecte o Android ao mesmo Wi-Fi e aponte para o IP desta
echo  maquina na porta 5001. Use http://localhost:5000 para
echo  configurar os botoes no navegador.
echo.
echo  [DICA] Pressione CTRL+C para encerrar o servidor.
echo.

cd /d "%~dp0server-windows"
node dist/index.js
pause
