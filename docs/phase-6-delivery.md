# Fase 6 — Operação Windows segura

## Entrega

- Servidor continua em loopback (`127.0.0.1`) por padrão.
- Bind remoto exige autenticação; a descoberta mDNS/DNS-SD é opt-in.
- Discovery exige IPv4 RFC1918 concreto, autenticação e anuncia apenas o serviço
  `_android-streamdeck._tcp.local.`, protocolo, porta e `requires_pairing`.
  Não publica código de pareamento, token, banco, caminho ou snapshot.
- `streamdeck-tray` controla apenas o processo servidor que ele cria, sem shell
  ou comando/caminho arbitrário. Menu: status, iniciar, parar e sair.
- Há scripts manuais e reversíveis de autostart e firewall. A regra de firewall
  é TCP de entrada apenas no perfil Private; não é aplicada automaticamente.
- PyInstaller produz `streamdeck-server.exe` e `streamdeck-tray.exe`. No bundle,
  o SQLite padrão fica em `%LOCALAPPDATA%\\AndroidStreamDeck`, fora do executável.

## Comandos

```bash
# Em server/
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync python scripts/build_windows.py
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync python scripts/smoke_windows_bundle.py
```

O smoke usa banco temporário e porta loopback efêmera; termina a árvore do
processo PyInstaller e confirma que a porta foi liberada.

## Evidências verificadas

- Servidor: `301 passed, 1 warning`; Ruff, `compileall`, `uv lock --check` e
  `git diff --check` aprovados. O warning é de depreciação externa do
  `starlette.testclient`/`httpx`.
- Bundle Windows real: `streamdeck-server.exe` (18.601.520 bytes) e
  `streamdeck-tray.exe` (16.284.065 bytes).
- Smoke do bundle: `health=ok; service=android-streamdeck-server; port_released=true`.
- Tray: backend `pystray` carregado e ícone Pillow 64×64 gerado.
- Android sem alteração funcional: debug, unit tests, lint, test APK e testes
  instrumentados executaram com sucesso no `Pixel_8`. Unit: 37/37. Instrumentado:
  3 executados sem falhas e 2 ignorados por exigirem `pairingCode` efêmero.

## Limites

O APK release mantém `usesCleartextTraffic=false`. A descoberta não autentica o
host, não substitui pareamento manual e não libera HTTP/WS em release. TLS/WSS,
consumo Android de mDNS e validação física no Galaxy A10 permanecem fora deste
escopo.
