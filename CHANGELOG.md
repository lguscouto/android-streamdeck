# Changelog

Todas as mudanças relevantes do Android Stream Deck são registradas aqui,
grupadas por fase funcional.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/) para
versões de produto; fases de desenvolvimento têm identificadores próprios.

## [Fase 11] — 2026-08-11 — Onboarding e controles essenciais

### Adicionado

- Onboarding versionado em três páginas, com pular, navegação, finalização e
  replay em Configurações; o replay é renderizado sobre o shell e preserva a
  sessão conectada.
- Direção visual Command Glow com ícones vetoriais/tintáveis, semântica de cor,
  estados de execução e grade 3 × 3.
- Fixture e perfil built-in `Controles essenciais` com Play/Pause, Próxima, Mute,
  Spotify, Chrome, Volume +, Volume −, Print Screen e uma célula livre.
- Migração v5 idempotente com marcador transacional, allowlist
  `PRINTSCREEN`/`VK_SNAPSHOT` e catálogo fechado `chrome` → `chrome.exe`.
- Executor de gravação opt-in para o harness, sem emissão de input real no
  Windows.

### Validado

- Servidor: **403 testes**, Ruff check/format, compileall, Bandit e lockfile.
- Android: `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`,
  `assembleRelease` unsigned e `lintDebug` com `BUILD SUCCESSFUL`.
- E2E HTTPS/WSS no `Pixel_8`: as três classes instrumentadas foram executadas,
  sem `failure`, `error` ou `skip`; `android_https_wss_e2e=ok`,
  `port_released=true` e `temporary_state_removed=true`.
- O executor `recording` impediu abertura do Chrome e emissão de input real no
  Windows; não restaram fixtures, screenshots ou bancos temporários.

### Limitações

- A leitura óptica física do QR e os efeitos reais de Chrome, mídia, volume e
  clipboard não foram executados; o gate usa fixtures e executor gravável.
- Release permanece unsigned sem keystore autorizada.


## [Fase 7] — 2026-08-11 — Pareamento simplificado

### Adicionado

- Sessão efêmera de pareamento com senha aleatória de 128 bits, validade de 10
  minutos, uso único, rotação e proteção contra replay.
- Bootstrap HTTPS autenticado pela prova derivada da senha, com CA e hostname
  validados antes do claim e do WebSocket WSS.
- Fluxo Android reduzido a IP privado, senha temporária e QR offline via
  CameraX/ML Kit; client ID, porta, CA, token e confiança TLS permanecem
  internos.
- Identidade do dispositivo gerada aleatoriamente e persistida com o Android
  Keystore; reconexão usa apenas token e confiança persistidos.

### Corrigido

- Harness E2E atualizado para a porta interna `8765`, `10.0.2.2`, bootstrap/
  claim, provas inválidas, replay, sessão desconhecida, ação WSS, edição e
  reconexão.
- Mensagens de ACK de ação são localizadas no Android e não exibem o texto
  inglês bruto do servidor.
- Validação estrutural e limite de tamanho do PEM da CA reforçados no servidor.

### Validado

- Suíte completa do servidor, Ruff, formatação, compilação e `uv lock --check`.
- `:app:testDebugUnitTest`, `:app:assembleDebug`,
  `:app:assembleDebugAndroidTest` e `:app:lintDebug`.
- E2E HTTPS/WSS no `Pixel_8`: 1/1 teste instrumentado aprovado,
  `android_https_wss_e2e=ok`, `port_released=true` e
  `temporary_state_removed=true`.

### Limitações

- O APK produzido nesta fase é debug assinado pela chave de debug do Android;
  o APK release depende de um keystore de distribuição autorizado.
- O fluxo de QR foi validado pelo payload estrito e pela integração offline do
  scanner; a leitura óptica com câmera física ainda requer validação dedicada.

## [Redesign visual] — 2026-08-11 — Command Surface

### Adicionado

- Tema de produto Compose com paleta Command Surface, tema claro/escuro,
  tokens de espaçamento/formas/tipografia e fonte Inter variável sob licença OFL.
- Deck com top bar compacta, status em pill, menu contextual, ícones vetoriais,
  contraste adaptativo, elevação, animação de pressão e estados de execução.
- Pareamento reorganizado em cartões de conexão e segurança, com progresso,
  estados de erro e seção avançada para CA PEM/código de confiança.
- Editor visual com preview vivo, seleção de tecla, ícones, paleta de cores,
  tipos de ação em menu e barra persistente de salvar/cancelar.
- Gestão de perfis/páginas em cartões com hierarquia para ativo, revisão e IDs.
- Importação por seletor nativo de arquivo JSON e exportação para arquivo,
  mantendo o preview/editável em memória antes de aplicar.
- Feedback tátil no pressionamento de comandos.

### Corrigido

- Declaração ausente de `ButtonExecutionState`, já referenciada pelo fluxo
  principal, restaurada no pacote de UI.
- Tema de navegação separado em `values-v27` para manter `minSdk 26` sem erro
  de lint.

### Validado

- `:app:testDebugUnitTest`, `:app:assembleDebug`, `:app:assembleDebugAndroidTest` e
  `:app:lintDebug` passaram; lint ficou em 0 erros e 10 warnings informativos.
- APK debug: `22.346.043` bytes; APK de testes: `442.790` bytes.
- Servidor: `361 passed, 1 warning`; Ruff, format, Bandit, pip-audit,
  compileall e `uv lock --check` passaram.
- E2E HTTPS/WSS real no `Pixel_8`: `android_https_wss_e2e=ok`,
  `port_released=true`, `temporary_state_removed=true`.
- Cinco screenshots PNG válidos, sem credenciais expostas, em `docs/visual/`
  (`1080×2400`): pareamento, deck principal, página secundária, editor e
  Settings.
- Reconexão validada com token criptografado persistido; o código efêmero
  continua obrigatório apenas no primeiro pareamento.

### Concluído

- Extração do shell para módulos por feature, Settings persistente, pager de
  páginas baseado no snapshot, preview SAF com confirmações e testes
  instrumentados/golden no emulador.

### Limitações externas

- Galaxy A10 ainda exige o aparelho físico.
- APK release continua unsigned; a distribuição exige keystore de produção
  externo.
- Commit, push e CI remoto são confirmados no relatório de publicação desta
  entrega.

## [Fase 10] — 2026-08-10 — Pendências do roadmap

### Corrigido

- **Concorrência na migração SQLite**: `Database.initialize()` não era
  serializado e podia quebrar migração sob corrida; agora roda sob lock por
  instância (descoberto pelo novo teste de concorrência).
- **Dependências vulneráveis (pip-audit)**: `cryptography 46.0.7` (4 CVEs,
  runtime TLS) → `50.0.0`; `pytest 8.4.2` (1 CVE) → `9.1.1`. Resultado:
  `No known vulnerabilities found`.

### Adicionado

- Testes de concorrência (`server/tests/test_concurrency.py`): limiter sob
  threads, reset por origem, escritas otimistas sem lost update, migração
  concorrente idempotente.
- Adaptador `application` fechado (`app/catalog.py` + `WindowsApplicationAdapter`):
  catálogo de binários sem paths, execução via `ShellExecuteW`, id fora do
  catálogo → rejeição; 8 testes.
- Acessibilidade: `liveRegion` em feedbacks (editor, gestão, status), `stateDescription`
  e `contentDescription` de seleção no editor, strings `a11y_*` PT-BR.
- Undo/retry no editor: botão "Reverter alterações" após falha de save
  (roadmap Fase 4), com teste unitário.
- CI: steps Bandit (`-ll`) e pip-audit no job server + Gitleaks scan.
- Benchmark de latência press→ack sobre WSS real:
  `server/scripts/phase10_latency_bench.py` — medição observada no loopback
  TLS: min 6,6 ms / mediana 7,2 ms / max 8,2 ms (5 iterações).
- Validação do caminho signed com keystore **descartável**:
  `server/scripts/phase10_sign_validation.py` (apksigner + aapt2 + cleanup;
  identidade de produção nunca criada).

### Validado

- Servidor: `361 passed`; Bandit sem issues; pip-audit zero vulns;
  Ruff/compile/lock/diff limpos.
- Android: `46` testes unit; lint `0` erros/`10` warnings (aceitas);
  builds OK; Pixel_8 abre sem crash; E2E Fase 7 reexecutado.
- Assinatura: `SIGNED_VALIDATION=ok` + `CLEANUP=done` (2×), sem resíduos.

### Restante (somente dependências externas)

- **Galaxy A10** (hardware) e **distribuição real assinada** (keystore de
  produção externo).

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