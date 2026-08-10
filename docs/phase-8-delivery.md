# Fase 8 — Release verificável

> Estado: **concluída e publicada** (verificar SHA no fim deste documento).
> Base da Fase 7: `149721369412ed8aaeba915d15454664988bac0a`.

## O que esta fase entrega

A Fase 8 transforma o estado funcional da Fase 7 em uma **entrega de release
reproduzível e auditável** para Windows e Android, sem colocar segredos, chaves
privadas, banco de runtime ou credenciais no repositório.

1. **Recursos empacotados corrigidos.** O servidor Windows agora resolve schemas
   e fixtures de uma única origem (`server/app/resources.py`) que funciona tanto
   no checkout-fonte quanto em um executável congelado (`sys._MEIPASS`). O bundle
   PyInstaller inclui `shared/protocol` e `shared/fixtures` inteiros. Antes, apenas
   o `default-profile.json` era empacotado e o schema de export/import quebrava no
   executável (`422 VALIDATION_ERROR` reproduzido em probe real).
2. **Smoke do bundle estendido.** `server/scripts/smoke_windows_bundle.py` agora
   prova, no executável congelado: health exato, export de perfil, import válido,
   encerramento da árvore de processo, porta liberada e remoção do diretório
   temporário.
3. **Manifesto de release determinístico.** `server/scripts/release_manifest.py`
   emite JSON com caminho lógico, tamanho e SHA-256 de cada artefato, commit,
   versões e estado de assinatura. Falha se um artefato obrigatório estiver
   ausente.
4. **Assinatura externa fail-closed (Android).** `android/app/build.gradle.kts`
   lê identidade de release apenas de um `release-signing.properties` não
   rastreado (ou variáveis `STREAMDECK_*`). Configuração **parcial** aborta o
   build; configuração **ausente** mantém o APK unsigned de forma honesta e
   explícita; o keystore Android Debug nunca é substituto de distribuição.
5. **Segurança de runtime.** `android:allowBackup=false` (o app persiste
   credenciais cifradas: token, CA, trust code) e `.gitignore` protege
   `*.jks`, `*.keystore`, `*.p12`, `*.pfx`, `local.properties`,
   `keystore.properties`, `signing.properties` e `**/release-signing.properties`.
6. **Documentação executável.** Este documento, `server/README.md` (atualizado) e
   `README.md` (atualizado) descrevem instalação, configuração de segurança,
   pareamento, atualização, reversão, hashes e limitações.

## Estados honestos do APK

| Estado | Como ocorre | Instalável? | Distribuível? |
|---|---|---|---|
| `app-debug.apk` | `assembleDebug` com keystore Android Debug | Sim (dev) | Não |
| `app-release-unsigned.apk` | `assembleRelease` sem identidade externa | **Não** (`INSTALL_PARSE_FAILED_NO_CERTIFICATES`) | Não |
| APK signed | `assembleRelease` com `release-signing.properties` completo | Sim | Somente após verificação `apksigner` do certificado esperado |

A tarefa `:app:printReleaseSigningStatus` reporta em texto:

```text
RELEASE_SIGNING=unsigned
```

quando não há identidade configurada, ou `RELEASE_SIGNING=configured` quando há.

## Assinatura de release (apenas com keystore autorizado)

Não foi criada, gerada nem embutida nenhuma chave de distribuição nesta fase. Para
assinar, um operador autorizado deve fornecer um keystore **fora do checkout** e
criar o arquivo ignorado `android/release-signing.properties`:

```properties
storeFile=C:/secure/path/release.jks
storePassword=[REDACTED]
keyAlias=android-streamdeck
keyPassword=[REDACTED]
```

Ou usar variáveis `STREAMDECK_STORE_FILE`, `STREAMDECK_STORE_PASSWORD`,
`STREAMDECK_KEY_ALIAS`, `STREAMDECK_KEY_PASSWORD`. O build falha fechado se
apenas parte dos campos estiver preenchida.

Verificação do APK assinado (nunca imprime senhas):

```bash
"$ANDROID_HOME/build-tools/35.0.0/apksigner.bat" verify --print-certs app-release.apk
"$ANDROID_HOME/build-tools/35.0.0/aapt2.exe" dump xmltree --file AndroidManifest.xml app-release.apk
```

O manifesto mesclado do release deve manter `usesCleartextTraffic=false` e
`allowBackup=false`.

## Instalação limpa (Windows)

1. **Pré-requisitos:** Windows 10/11 x64, JDK/JBR 17+ apenas para builds
   AOSP/Gradle; para o servidor, o bundle é autocontido.
2. **Obter o bundle:** `server/dist/streamdeck-server.exe` e
   `server/dist/streamdeck-tray.exe` (construídos em
   `server/scripts/build_windows.py`).
3. O servidor, quando congelado, usa `%LOCALAPPDATA%\AndroidStreamDeck` para
   banco SQLite (`streamdeck.sqlite3`) e estado TLS (`tls/`). Nada mutável fica
   em `dist/` ou na extração temporária do PyInstaller.

### Segurança de transporte (loopback x LAN)

- **Loopback (padrão):** `STREAMDECK_HOST=127.0.0.1`, TLS opcional.
- **LAN (remote bind):** `STREAMDECK_HOST=0.0.0.0` exige `STREAMDECK_REQUIRE_AUTH=true`
  e `STREAMDECK_TLS_MODE=required`; ver `server/README.md` e
  [`docs/architecture.md`](architecture.md).
- A CA pública e o trust code (spki) são obtidos **fora de banda** do estado TLS;
  mDNS é discovery opt-in e não é raiz de confiança.

### Pareamento e administração

- Pareamento usa pairing code separado do código administrativo e aplica rate
  limiting por origem.
- Revogação e reparing fecham imediatamente WebSockets existentes
  (`AUTH_REVOKED`/código `1008`) e invalidam credenciais por `credential_generation`.
- As respostas administrativas são sanitizadas (`[REDACTED]`).

## Atualização e reversão (preservando dados)

O bundle anterior é substituível sem apagar `%LOCALAPPDATA%\AndroidStreamDeck`:
banco, CA, pares e credenciais continuam válidos se o endpoint/identidade TLS não
mudar. Procedimento de reversão:

1. Pare o servidor (menu da bandeja ou `taskkill` da árvore própria).
2. Substitua os `.exe` em `server/dist` (ou onde o operador os mantém) pelo
   bundle anterior.
3. Inicie novamente. O banco e o estado TLS antigos são reutilizados.
4. Se a identidade TLS tiver mudado, o Android exige re-trust via bootstrap fora
   de banda (não há trust-on-first-use).

## Manifesto de release

Gerar (a partir do checkout final):

```bash
cd E:/projetos/android-streamdeck/server
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync python -m scripts.release_manifest
```

Saída (hashes observados nesta fase):

```text
server.exe    22.239.012 bytes  SHA-256 98ebc90ec9a95b6c9ccb3bb2237243e4fe42244d2a6930890ff093a2a61dbf8a
tray.exe      19.916.796 bytes  SHA-256 03de91b89ae6b3028e48c9c93c27437141b7f7f42d1077785bed042c28222a90
app-release-unsigned.apk  7.229.204 bytes  SHA-256 444c96c60fcbc26e5f4ae96ad58b52477ceb1dc9d82c4b1d04fc3e51581a2ceb
```

> Hashes exatos são obtidos executando o script; os valores acima são a
> observação registrada ao final da fase. O manifesto não contém segredos,
> timestamps obrigatórios, banco, CA ou chaves.

## Validação executada nesta fase

| Gate | Resultado |
|---|---|
| Servidor `pytest -q` | `333 passed, 1 warning` |
| Ruff format/check, compileall, `uv lock --check`, `git diff --check` | aprovados |
| SMOKE bundle (health, export, import, porta liberada, dir removido) | `health=ok; export=ok; import=ok; port_released=true; temporary_state_removed=true` |
| Android unit `testDebugUnitTest` | `44 tests, 0 failures` |
| Android `lintDebug` | `0 errors, 13 warnings` (GradleDependency/ComposableNaming/ObsoleteSdkInt/DataExtractionRules informativos) |
| `assembleDebug`/`assembleRelease` | BUILD SUCCESSFUL |
| `printReleaseSigningStatus` (sem keystore) | `RELEASE_SIGNING=unsigned` |
| Fail-closed config parcial | `BUILD FAILED` com mensagem explícita |
| Manifesto mesclado release | `allowBackup=false`, `usesCleartextTraffic=false` |
| `apksigner` no release unsigned | `DOES NOT VERIFY` (estado honesto) |
| Instalação release unsigned no Pixel_8 | bloqueada pelo Android (esperado; sem assinatura não instala) |
| Instalação debug + launch no Pixel_8 | Success, `topResumedActivity=MainActivity`, sem `FATAL EXCEPTION` |
| Smoke TLS Fase 7 | `https_health=ok; port_released=true` |
| E2E Android HTTPS/WSS Fase 7 (Pixel_8) | `android_https_wss_e2e=ok; port_released=true; temporary_state_removed=true` |

## Limitações

- O **APK release continua unsigned** e, portanto, não distribuível nem
  instalável; assinatura exige um keystore externo autorizado (fora do escopo
  desta fase).
- **Galaxy A10 não validado fisicamente**; o único destino validado é
  `Pixel_8`/API 35.
- O cliente Android mantém **endpoint manual** (HTTPS/WSS); mDNS é apenas
  discovery auxiliar e não é raiz de confiança.
- CI (GitHub Actions) ainda não automatiza os gates; a execução foi manual e
  registrada neste documento.
- `R8/proguard-rules.pro` está referenciado no buildType release, mas
  `isMinifyEnabled=false`; não há shrinking ativo.

## Verificação de publicação

Após o commit, confirmar:

```bash
git rev-parse HEAD          # SHA local
git ls-remote origin refs/heads/master | cut -f1   # SHA remoto
git status --short --branch
```

A Fase 8 só é considerada publicada quando os dois SHAs coincidem.