# Entrega da Fase 2 — pareamento e transporte autenticado

**Data:** 2026-08-09
**Escopo:** pareamento Android–Windows, token opaco, autenticação WebSocket,
sincronização inicial de perfil e armazenamento seguro da credencial no Android.

## Entregue

- `POST /api/v1/pairing/claim` valida um código de pareamento configurado fora do
  Git e emite um token opaco aleatório.
- O SQLite do servidor persiste somente o SHA-256 do token. Um novo pareamento do
  mesmo `client_id` substitui a credencial anterior.
- O WebSocket exige `hello.payload.access_token` quando a autenticação está ativa;
  token ausente ou inválido é rejeitado antes da leitura do perfil.
- O cliente Android normaliza o endpoint HTTP/HTTPS, usa OkHttp para o claim e
  WebSocket e apresenta conexão, autenticação e revisão do perfil.
- O token é cifrado no Android com AES-GCM. A chave é criada e mantida no Android
  Keystore, não é exportável e a credencial é vinculada ao endpoint normalizado
  que a emitiu.
- Alterar o servidor ou o identificador do cliente remove a credencial local, para
  que ela não seja enviada a outro endpoint.
- HTTP/WS sem TLS está liberado apenas no manifesto `debug`; o APK release gerado
  declara `usesCleartextTraffic=false`.

## Evidências verificadas

### Servidor

```text
pytest: 169 passed, 1 warning
ruff: passed
compileall: passed
uv lock --check: passed
```

O warning é externo à Fase 2: `StarletteDeprecationWarning` sobre a dependência
`httpx` usada por `starlette.testclient`.

### Android

A grade final passou:

```text
:app:testDebugUnitTest
:app:lintDebug
:app:assembleDebug
:app:assembleRelease
:app:assembleAndroidTest
:app:connectedDebugAndroidTest
```

O teste instrumentado do Keystore gravou e recarregou credenciais reais no AVD e
confirmou que as três entradas persistidas seguem o envelope cifrado `v1:` sem
conter o token em texto claro.

O smoke E2E explícito foi executado no AVD `Pixel_8` (`emulator-5554`) contra um
servidor temporário em `0.0.0.0:8765`, com código de pareamento aleatório mantido
somente em memória. O relatório XML registrou dois testes, sem falhas:

- `storesCredentialsEncryptedAndReloadsThem`;
- `pairsSynchronizesAndReconnectsWithEncryptedToken`.

O segundo teste preencheu o formulário com UiAutomator nativo, confirmou os
estados `Conectado`, `Servidor autenticado` e `Perfil sincronizado na revisão 1`,
verificou a persistência cifrada e reiniciou a atividade para validar a reconexão
sem reenviar o código. Ao final, o servidor, o banco temporário e os dados do
emulador foram removidos; a porta `8765` não permaneceu em escuta.

## Artefatos

- APK debug validado: `android/app/build/outputs/apk/debug/app-debug.apk`
  - 10.627.894 bytes
  - instalável para desenvolvimento e smoke local
- APK release gerado: `android/app/build/outputs/apk/release/app-release-unsigned.apk`
  - 7.126.300 bytes
  - **não assinado para distribuição**

Metadados verificados no APK debug:

```text
applicationId: br.com.gustavo.streamdeck
versionCode: 1
versionName: 0.1.0
minSdk: 26
targetSdk: 35
compileSdk: 35
```

## Limites assumidos conscientemente

- A validação ocorreu no `Pixel_8` AVD (API 37), não no Galaxy A10 físico.
- A Fase 2 estabelece o canal seguro de pareamento e sincronização; a execução de
  ações continua bloqueada e pertence à Fase 3.
- TLS/mTLS, descoberta segura, rotação administrativa e revogação por interface
  permanecem como hardening posterior. O servidor não deve ser exposto à internet.
