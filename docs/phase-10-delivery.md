# Fase 10 — Pendências do roadmap (consolidação)

> Estado: **concluída**; commit, push, confirmação do SHA remoto e CI fazem parte da validação final desta entrega.
> Base: Fase 9 (`e54d4dbdd3ca2df1c87ba6d5b8311d95a7129ef4`).

## O que esta fase entregou

Fechou **todos os itens pendentes do roadmap** que não dependiam de hardware ou
de um keystore de produção.

### 1. Concorrência do servidor (Fase 7)

- Novos testes em `server/tests/test_concurrency.py`:
  - `AttemptRateLimiter` sob contenção de threads (30 tentativas, 8 workers →
    exatamente `max_attempts` permitidas);
  - reset por origem sem afetar outras;
  - escritas otimistas em SQLite preservam revisões monótonas sem lost update
    (retry saudável em conflito);
  - migração concorrente idempotente (uma instância compartilhada).
- **Correção real descoberta pelo teste**: `Database.initialize()` não era
  serializado e podia quebrar migração sob corrida (`BEGIN`/DDL); agora a
  migração roda sob o lock por instância (`server/app/db.py`), compatível com o
  modelo single-process.

### 2. SAST/dependency-audit no CI (Fase 7/9)

- `bandit>=1.8` e `pip-audit>=2.8` adicionados ao dev group + lock.
- **`pip-audit` encontrou 5 vulnerabilidades reais** no baseline:
  - `cryptography 46.0.7` → 4 CVEs; atualizado para `>=48,<52` (resolved
    **50.0.0**) — era runtime TLS;
  - `pytest 8.4.2` → 1 CVE; atualizado para `>=9.0,<10` (resolved **9.1.1**).
- Resultado pós-fix: **`No known vulnerabilities found`**; suíte `361 passed`.
- Bandit: **`No issues identified`** (Medium 0, High 0) após `# nosec`
  justificados em 3 falsos positivos de scripts de teste (0.0.0.0 intencional no
  E2E Android; `urlopen` loopback no smoke do bundle).
- Workflow `gates.yml` ganhou os passos `Bandit security scan`,
  `pip-audit dependency vulnerabilities` e `Gitleaks secret scan`
  (`gitleaks/gitleaks-action@v2`).

### 3. Adaptador `application` fechado (Fase 4)

- `server/app/catalog.py`: `ApplicationCatalog` com executáveis **só nome de
  binário** (sem separadores de path, `..`, drives) e inventory público sem
  caminhos.
- `server/app/actions.py`: `WindowsApplicationAdapter` resolve `app_id` pelo
  catálogo e lança via `ShellExecuteW` (nunca shell); id fora do catálogo →
  `ActionExecutionRejected("Application is not enabled")`.
- `ActionRegistry` ganhou o adaptador (o `application` já estava no catálogo de
  tipos do protocolo — agora tem execução real, mas **fail-closed**).
- 8 testes (`server/tests/test_application_catalog.py`): resolução, listing
  sem path, lançamento com mock, rejeição de id desconhecido, rejeição de
  caminho, propagação de falha, catálogo rejeita paths.

### 4. Acessibilidade Android (Fase 7)

- `contentDescription`/`semantics` já existiam na grade; agora:
  - editor: botões de seleção com `stateDescription` ("Selecionado") e
    `contentDescription` de ação ("Selecionar botão X"); erro com
    `liveRegion=Polite`;
  - gestão de perfis: sucesso/erro com `liveRegion=Polite`;
  - tela principal: `statusMessage` com `liveRegion=Polite`;
  - strings `a11y_*` centralizadas em `strings.xml` (PT-BR).

### 5. Undo/retry no editor (Fase 4)

- `App.kt`: `editorOriginalDraft` capturado em `startEditing()`;
  `revertEditing()` restaura o draft original e limpa o erro;
  botão **"Reverter alterações"** aparece no editor quando há mudanças a
  reverter (visível também em erro de save).
- Teste unitário `ProfileEditorDraftTest` valida que restaurar o draft original
  reproduz exatamente o snapshot inicial.

### 6. Bateria/latência de press (Fase 7)

- `server/scripts/phase10_latency_bench.py`: benchmark reproduzível do RTT
  `press→ack` sobre **WSS autenticado real** (servidor TLS descartável +
  pareamento real por `POST /pairing/claim`).
- **Medição observada nesta máquina** (loopback TLS, Pixel_8/emulador não
  envolvido no caminho de rede): 5 iterações → **min 6,6 ms; mediana 7,2 ms;
  max 8,2 ms**. É uma observação, não uma garantia.
- Guia no final deste documento.

### 7. Caminho signed validado (Fase 8)

- `server/scripts/phase10_sign_validation.py`: gera keystore **temporário**
  fora do checkout, escreve `release-signing.properties` ignorado, roda
  `assembleRelease`, verifica com `apksigner` + `aapt2`, e **remove tudo** em
  `finally`.
- **Resultado real da validação**: `RELEASE_SIGNING=configured`, APK
  `app-release.apk` (7.238.880 B) verificado pelo `apksigner` (certificado
  temporário, SHA-256 `b2b091882b989b2387a5eed46a7bd8674d6e2d7ee110d7e53d713320c5a374a0`),
  manifesto mesclado com `versionCode 1 / versionName 0.1.0`,
  `allowBackup=false`, `usesCleartextTraffic=false`, `dataExtractionRules`;
  cleanup confirmado (keystore, props e tempdir removidos; `git status` limpo).
- **Decisão registrada**: identidade **descartável de validação** — não é
  keystore de produção e nunca será reutilizada.

## Validação executada

| Gate | Resultado |
|---|---|
| Servidor `pytest -q` | `361 passed, 1 warning` (349 → 361) |
| Bandit `-ll -r app scripts` | `No issues identified` (Medium/High 0) |
| pip-audit | `No known vulnerabilities found` (5 CVEs corrigidas na fase) |
| Ruff/compileall/`uv lock --check`/diff | aprovados |
| Android unit | `46 tests, 0 failures` (45 → 46) |
| Android lint | `0 errors, 10 warnings` (inalteradas/aceitas) |
| `assembleDebug`/`assembleRelease` (`--rerun-tasks`) | BUILD SUCCESSFUL |
| `printReleaseSigningStatus` | `RELEASE_SIGNING=unsigned` (sem keystore) |
| Pixel_8 install + launch | Success, `topResumedActivity=MainActivity`, sem `FATAL EXCEPTION` |
| E2E Fase 7 (definitivo) | `android_https_wss_e2e=ok; port_released=true; temporary_state_removed=true` (3 execuções finais verdes) |
| Validação signed descartável | `SIGNED_VALIDATION=ok` + `CLEANUP=done` (2×) |
| Benchmark latência | `min 6.6 / mediana 7.2 / max 8.2 ms` (5 iterações WSS loopback) |

### Diagnóstico registrado (E2E instrumentado)

Durante a Fase 10, o E2E instrumentado da Fase 7 passou a falhar em
`assertEditorSave` (editor permanecia aberto; "Perfil salvo na revisão 2" não
aparecia). A causa raiz identificada empiricamente: **o IME aberto** após
`setText()` cobria a metade inferior da tela (edge-to-edge + insets), e o botão
"Salvar perfil" — visível na árvore de acessibilidade mas sob o teclado —
recebia um toque no-op. Correções testadas até o padrão estável:

- `pressBack` condicional por foco: instável (poderia fechar a Activity sem IME).
- Heurística de "centro da tela": agressiva demais (quebrava botões legítimos em
  posição inferior).
- **Final (estável, 3 execuções verdes):** `input keyevent 111` (ESCAPE) enviado
  antes de cada `tapByText` — fecha o IME sem navegar de volta; depois o alvo é
  localizado normalmente e clicado.

## Guia de benchmark de latência

```bash
cd E:/projetos/android-streamdeck/server
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync \
  python scripts/phase10_latency_bench.py
# Parâmetros: PHASE10_LATENCY_ITERATIONS (padrão 5)
```

Para bateria: conectar o aparelho e usar `adb shell dumpsys battery` (level,
status) e `adb shell dumpsys batterystats` para uma sessão de uso da grade;
relatar nível consumido por período. No emulador não há bateria física, então o
benchmark de latência é a medição objetiva registrada.

## Validação signed (reproduzível, sem segredos)

```bash
cd E:/projetos/android-streamdeck/server
export JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'
export ANDROID_HOME='C:/Users/gustavo/AppData/Local/Android/Sdk'
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync \
  python scripts/phase10_sign_validation.py
```

O script não deixa resíduos: remove keystore temporário, propriedades e
tempdir. A identidade é descartável e não constitui distribuição.

## O que resta após esta fase (somente dependências externas)

- **Galaxy A10**: bloco de validação documentado; execução exige o aparelho.
- **Distribuição real assinada**: exige um keystore de produção externo;
  a pipeline fail-closed e a validação descartável provam o caminho completo.

## Verificação de publicação

```bash
git rev-parse HEAD
git ls-remote origin refs/heads/master | cut -f1
git status --short --branch
gh run list --workflow=gates --limit 3
```