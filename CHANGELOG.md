# Changelog

Todas as mudanças relevantes do Android Stream Deck são registradas aqui,
agrupadas por fase funcional.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/) para
versões de produto; fases de desenvolvimento têm identificadores próprios.

## [Fase 9] — 2026-08-10 — CI sem segredos e hardening de borda/observabilidade

### Adicionado

- **CI GitHub Actions** (`.github/workflows/gates.yml`): jobs `server` (ubuntu,
  uv --locked, pytest 349/2 skips NTFS, ruff, compileall, lock), `android`
  (JDK 17 + SDK 35, unit/lint/assemble + gate `RELEASE_SIGNING=unsigned`) e
  `windows-bundle` (windows-latest, PyInstaller + smoke), com
  `permissions: contents: read` e zero segredos; `gradlew` com bit de execução
  para o runner Linux.
- **Logs estruturados JSON sem segredos** (`server/app/logging_config.py`):
  formatter JSON, `RotatingFileHandler` em `%LOCALAPPDATA%\AndroidStreamDeck\logs`,
  middleware de access-log sanitizado (`HTTP_ACCESS`) e eventos de segurança
  como códigos estáveis (`DEVICE_REVOKED`, `WS_AUTH_FAILED`); teste `caplog`
  garante que pairing/admin/token nunca aparecem.
- **Cap global de payload** (`server/app/body_limit.py`): 413 `PAYLOAD_TOO_LARGE`
  em `POST/PUT/PATCH` acima de 1 MiB, antes do parse Pydantic (o import mantém
  seu cap próprio de 512 KiB).
- **Rate limit de handshake WebSocket por origem** (`AttemptRateLimiter` 5/60s,
  fechamento `1013 RATE_LIMITED`) sem afetar outras origens.
- **Fonte única de metadados Android**: `buildConfig=true` +
  `buildConfigField`; `AppMetadata` lê de `BuildConfig`; teste anti-drift.
- **Backup seguro**: `res/xml/data_extraction_rules.xml` exclui tudo
  (cloud-backup e device-transfer) + `fullBackupContent=false` +
  `android:dataExtractionRules` — cobre transferência device-to-device.
- **Edge-to-edge (targetSdk 35)**: `enableEdgeToEdge()` + `safeDrawing` insets
  + formulários roláveis; tema sem `statusBarColor`/`navigationBarColor` legados.
- **Lint**: `lint { checkDependencies = true }`; 13 → 10 warnings (eliminadas
  2 `ComposableNaming` e 1 `DataExtractionRules`; restam 9 `GradleDependency` e
  1 `ObsoleteSdkInt` aceitas e documentadas).
- `android/app/proguard-rules.pro` (guarda para futuro R8; minify continua off).
- `release_manifest.py` lê commit real (`GITHUB_SHA` → `git rev-parse`).

### Validado

- Servidor: `349 passed`; Ruff/lint/compile/lock/diff limpos.
- Bundle: `health=ok; export=ok; import=ok; port_released=true; temporary_state_removed=true`.
- Android: `45` testes unit, `0` falhas; lint `0` erros; manifesto release com
  `allowBackup=false`, `fullBackupContent=false`, `usesCleartextTraffic=false`
  e `dataExtractionRules`; Pixel_8 abre sem crash.
- E2E Fase 7 reexecutado: `https_health=ok`; `android_https_wss_e2e=ok`.
- **CI real no GitHub**: primeira rodada revelou 2 testes sensíveis a
  `os.pathsep` (falhavam só no Linux); corrigido e rodada final verde —
  Server 20s, Android 2m55s, Windows bundle 1m6s.

### Pendente / limitações

- APK release continua **unsigned**; Galaxy A10 não validado fisicamente.

## [Fase 8] — 2026-08-10 — Release verificável

### Corrigido

- **Recursos do bundle Windows.** Schemas e fixtures agora são resolvidos por um
  único resolvedor (`server/app/resources.py`) que funciona em fonte e em bundle
  congelado (`sys._MEIPASS`). O PyInstaller empacota `shared/protocol` e
  `shared/fixtures` inteiros. Antes da correção, exportar/importar perfil no
  executável congelado falhava com `422 VALIDATION_ERROR` porque apenas o
  `default-profile.json` era empacotado.
- **Smoke do bundle.** O script agora prova health, export e import reais no
  executável, além do encerramento da árvore de processo, porta liberada e
  remoção do diretório temporário.

### Adicionado

- Manifesto/verificador de release determinístico (`server/scripts/release_manifest.py`).
- Assinatura Android externa **fail-closed** (`android/app/build.gradle.kts`):
  configuração parcial aborta o build; ausente mantém o APK release unsigned de
  forma explícita; tarefa `:app:printReleaseSigningStatus` reporta o estado.
- `.gitignore` protegendo `*.jks`, `*.keystore`, `*.p12`, `*.pfx`,
  `local.properties`, `keystore.properties`, `signing.properties` e
  `**/release-signing.properties`.
- `android:allowBackup=false` para não expor credenciais cifradas (token, CA,
  trust code) ao mecanismo de backup do Android.
- Documentação de release (`docs/phase-8-delivery.md`), changelog e atualização
  de `README.md`, `server/README.md` e `shared/protocol/README.md`.

### Validado

- Servidor: `333 passed`; Ruff/lint/compile/lock/diff limpos.
- Bundle: `health=ok; export=ok; import=ok; port_released=true; temporary_state_removed=true`.
- Android: `44` testes unitários, `0` falhas; lint `0` erros;
  `assembleDebug`/`assembleRelease` OK; manifesto mesclado com
  `usesCleartextTraffic=false` e `allowBackup=false`.
- Emulador Pixel_8: APK debug instala e abre (topResumedActivity), sem
  `FATAL EXCEPTION`. APK release unsigned é corretamente bloqueado pelo Android
  (`INSTALL_PARSE_FAILED_NO_CERTIFICATES`).
- E2E Fase 7 reexecutado: `https_health=ok`; `android_https_wss_e2e=ok`.

### Pendente / limitações

- APK release permanece **unsigned** (exige keystore externo autorizado).
- Galaxy A10 não validado fisicamente.
- CI automatizado dos gates foi entregue na Fase 9.

## [Fase 7] — 2026-08-10 — TLS/WSS e administração de dispositivos

### Corrigido (hotfix pós-publicação)

- Revogação e reparing fecham **imediatamente** sessões WebSocket existentes
  (`AUTH_REVOKED`, código `1008`) e invalidam credenciais por
  `credential_generation`, em vez de apenas bloquear a próxima ação.
- Rate limiting por origem para pareamento e administração
  (`PAIRING_RATE_LIMITED`, `DEVICE_ADMIN_RATE_LIMITED`), resposta sanitizada
  `429`.

### Adicionado

- Administração separada do pareamento, com código próprio e respostas
  sanitizadas (`[REDACTED]`).

### Validado

- `326 passed`; smoke TLS `https_health=ok`; E2E Android HTTPS/WSS
  `android_https_wss_e2e=ok`.