# Fase 9 — CI sem segredos e hardening de borda/observabilidade

> Estado: **concluída e publicada** (verificar SHA no fim deste documento).
> Base da Fase 8: `1592d8f05598715de4d2bbb56a2b7ed6d58bbe37`.

## O que esta fase entrega

1. **CI automatizado no GitHub Actions (`gates.yml`)** com três jobs sem segredos:
   - `server` (ubuntu-latest): `uv sync --locked`, `pytest -q` (baseline:
     349 testes, 2 skips NTFS-only em `test_tls.py`), `ruff format --check`,
     `ruff check`, `compileall`, `uv lock --check`.
   - `android` (ubuntu-latest, JDK 17 temurin, SDK 35 via `sdkmanager`):
     `testDebugUnitTest`, `lintDebug`, `assembleDebug`, `assembleRelease`,
     e um gate explícito que prova `RELEASE_SIGNING=unsigned` (CI nunca assina).
   - `windows-bundle` (windows-latest, em `push` para `master` e
     `workflow_dispatch`): build PyInstaller + smoke do executável congelado.
   - `permissions: contents: read`, sem secrets, `concurrency` para cancelar
     runs obsoletos; `gradlew` recebeu bit de execução (`100755`) para rodar no
     runner Linux.
2. **Logs estruturados JSON sem segredos (servidor).**
   - Novo `server/app/logging_config.py`: formatter JSON (`time`, `level`,
     `logger`, `event`, extras seguros), `dictConfig` com `RotatingFileHandler`
     em `%LOCALAPPDATA%\AndroidStreamDeck\logs\server.log` (estado mutável, fora
     do bundle/checkout); `STREAMDECK_LOG_DIR` permite override em fonte.
   - Middleware sanitizado de access-log (`HTTP_ACCESS`) em `main.py`: apenas
     método, path, status, duração e origem — nunca headers de auth, token,
     pairing/admin code ou corpo. Uvicorn usa `log_config=None` (o acesso vem do
     middleware, com formato nosso).
   - Eventos de segurança como códigos estáveis, sem valores: `DEVICE_REVOKED`,
     `WS_AUTH_FAILED`, `WS_RATE_LIMITED`. Teste `caplog` prova que pairing code,
     admin code e token não aparecem em nenhum registro.
3. **Hardening de borda (servidor).**
   - **Cap global de payload** (`server/app/body_limit.py`): `POST/PUT/PATCH` com
     corpo acima de 1 MiB retornam `413 PAYLOAD_TOO_LARGE` sanitizado antes do
     parse Pydantic (protege as rotas de escrita autenticadas além do import,
     que já tinha cap próprio de 512 KiB). Cobra também streaming/chunked sem
     `Content-Length`.
   - **Rate limit de handshake WebSocket por origem**: `WebSocketManager` agora
     recebe um `handshake_rate_limiter` (`AttemptRateLimiter`, 5/60s) e
     `_serve_websocket` fecha com `1013`/`RATE_LIMITED` quando a origem excede a
     janela — sem afetar outras origens. Limiter in-memory (reset em restart),
     aceitável para servidor local single-process.
4. **Hardening Android.**
   - **Fonte única de metadados**: `buildConfig = true` + `buildConfigField`
     para `APPLICATION_ID`/`VERSION_CODE`/`VERSION_NAME`; `AppMetadata.kt` agora
     lê de `BuildConfig` (mantém os nomes originais e aliases lower-case); novo
     teste `AppMetadataTest` trava o drift Gradle ↔ BuildConfig ↔ AppMetadata.
   - **Backup/extração**: `res/xml/data_extraction_rules.xml` exclui **tudo**
     (cloud-backup e device-transfer); manifesto ganhou
     `android:dataExtractionRules` e `android:fullBackupContent="false"` — cobre
     a transferência device-to-device que `allowBackup=false` sozinho não bloqueia
     no Android 12+; warning `DataExtractionRules` eliminado do lint.
   - **Edge-to-edge (targetSdk 35 enforcement)**: `enableEdgeToEdge()` na
     `MainActivity`, `windowInsetsPadding(WindowInsets.safeDrawing)` na `Surface`
     raiz, remoção de `statusBarColor`/`navigationBarColor`/`windowLightStatusBar`
     do tema; formulários e editor ficaram roláveis (`verticalScroll`) para o
     conteúdo respeitar as barras do sistema. Validação no Pixel_8 confirmou que
     o conteúdo não fica sob as system bars e o clone do teste instrumentado
     (que exigia ajustes de scroll/IME) passa.
   - **Lint-zero parcial**: renomeados `actionValueField` → `ActionValueField` e
     `numberField` → `NumberField` (warnings `ComposableNaming` eliminadas);
     `lint { checkDependencies = true }`. Restam 10 warnings aceitas e
     documentadas: 9 `GradleDependency` (upgrades exigiriam AGP/Kotlin mais novos;
     decisão registrada) e 1 `ObsoleteSdkInt` (`mipmap-anydpi-v26` — qualificador
     necessário para fallback do adaptive icon no launcher; a tentativa de mover
     para `mipmap-anydpi` quebra o AAPT, revertido).
5. **Higiene.**
   - `android/app/proguard-rules.pro` criado (guarda para futuro R8; não habilita
     minify).
   - `server/scripts/release_manifest.py` lê commit real (`GITHUB_SHA` no CI ou
     `git rev-parse HEAD` local; fallback `unknown`), com testes.
   - `gradlew` com bit de execução para runner Linux.

## Decisões registradas

| Decisão | Motivação |
|---|---|
| `isMinifyEnabled=false` mantido; `proguard-rules.pro` criado | Sem keystore não há como validar APK minificado em device; o arquivo evita quebra futura se R8 for habilitado |
| 9 warnings `GradleDependency` não fixadas | Updates sugeridos (activity 1.13.0, compose 1.11.4, material3 1.4.0) podem exigir AGP/Kotlin mais novos que 8.8.2/2.0.21; risco de quebra > benefício |
| `mipmap-anydpi-v26` mantido | Tentativa `mipmap-anydpi` quebra `processDebugResources` (AAPT); warning `ObsoleteSdkInt` aceita como não-bloqueadora |
| Rate limit WS in-memory | Servidor local single-process; reset em restart documentado |

## Validação executada

| Gate | Resultado |
|---|---|
| Servidor `pytest -q` | `349 passed, 1 warning` (333 → 349; +16 entre Fase 8→9) |
| Ruff format/check, compileall, `uv lock --check`, `git diff --check` | aprovados |
| Bundle rebuild | `server.exe` 22.245.702 B, `tray.exe` 20.276.147 B |
| Smoke bundle | `health=ok; export=ok; import=ok; port_released=true; temporary_state_removed=true` |
| Android unit | `45 tests, 0 failures` (44 → 45, +BuildConfig drift) |
| Android lint | `0 errors, 10 warnings` (era 13; eliminadas 2 ComposableNaming + 1 DataExtractionRules) |
| `assembleDebug`/`assembleRelease` (`--rerun-tasks`) | BUILD SUCCESSFUL |
| `printReleaseSigningStatus` | `RELEASE_SIGNING=unsigned` (honesto, sem segredos) |
| Manifesto release mesclado | `allowBackup=false`, `fullBackupContent=false`, `usesCleartextTraffic=false`, `dataExtractionRules=@xml/data_extraction_rules` |
| Pixel_8 install + launch | Success, `topResumedActivity=MainActivity`, sem `FATAL EXCEPTION` |
| Smoke TLS Fase 7 | `https_health=ok; port_released=true` |
| E2E Android HTTPS/WSS Fase 7 (Pixel_8) | `android_https_wss_e2e=ok; port_released=true; temporary_state_removed=true` |

## Como validar o CI

Após o push desta fase, o workflow `gates` dispara automaticamente:

```bash
gh run list --workflow=gates --limit 5
gh run view <run-id>
```

Os jobs `server` e `android` rodam em PRs e push; `windows-bundle` em push para
`master` e `workflow_dispatch`. A primeira execução real deve ser observada e
seus resultados registrados aqui (tempos, skips, licenças SDK); ajustes no
workflow, se necessários, são pequenos e seguem o mesmo fluxo.

## Limitações

- Instrumented E2E Android (real, com emulador/device) e Galaxy A10 continuam
  manuais e fora do CI (exigem hardware).
- APK release segue **unsigned**; distribuição exige keystore externo autorizado.
- As 10 warnings de lint restantes são aceitas e documentadas.
- Release manifest permanece etapa de release manual/dispatch (exige os 3
  artefatos), não gate de PR.

## Verificação de publicação

Após o commit:

```bash
git rev-parse HEAD                # SHA local
git ls-remote origin refs/heads/master | cut -f1   # SHA remoto
git status --short --branch
gh run list --workflow=gates --limit 5   # CI disparado
```

A Fase 9 só é considerada publicada quando os dois SHAs coincidem e o CI foi
observado.