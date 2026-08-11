# Fase 11 — Onboarding, Command Glow e controles essenciais

## Escopo

Este incremento adiciona uma experiência de primeira execução no Android e um
perfil inicial útil, sem alterar o protocolo de pareamento seguro já entregue.
O fluxo continua offline-first no cliente e fail-closed no servidor.

Entregas:

- onboarding versionado (`onboardingVersion = 1`) com três páginas, voltar,
  próximo, pular, finalização e replay em Configurações;
- overlay de onboarding sobre o shell existente, preservando socket/snapshot
  quando o tutorial é reaberto;
- tema Command Glow com vetores Compose/Material Icons, tint semântico, bordas
  de accent, estados de execução e célula vazia não interativa;
- perfil built-in `essential-controls`, `Controles essenciais`, com uma página
  `Principal` 3 × 3 e oito controles;
- instalação transacional/idempotente do perfil, sem sobrescrever perfil ativo
  ou personalizado e sem recriar uma exclusão voluntária;
- allowlist `PRINTSCREEN` → `VK_SNAPSHOT` (`0x2C`) com down/up;
- catálogo fechado `chrome` → `chrome.exe`, sem caminho ou argumentos do
  cliente, com listagem pública sem o nome do executável;
- executor de gravação opt-in usado apenas pelo harness isolado, sem efeitos
  no Windows;
- stores instrumentados usam namespace descartável no APK debug, sem limpar o
  `SharedPreferences` real do usuário;
- atualização de fixtures, testes instrumentados, documentação e gates locais.

## Perfil essencial

| Posição | Rótulo | Ação |
| --- | --- | --- |
| 0,0 | Play/Pause | `media/play_pause` |
| 0,1 | Próxima | `media/next` |
| 0,2 | Mute | `media/mute` |
| 1,0 | Spotify | `media/play_pause` |
| 1,1 | Chrome | `application/chrome` |
| 1,2 | Volume + | `media/volume_up` |
| 2,0 | Volume − | `media/volume_down` |
| 2,1 | Print Screen | `key/PRINTSCREEN` |
| 2,2 | vazio | não clicável |

Spotify usa a sessão multimídia global do Windows; não há OAuth nem garantia de
exclusividade. Print Screen coloca a captura no clipboard pelo comportamento do
Windows, mas o servidor não salva, transmite ou registra a imagem.

## Validação executada

### Servidor

Executado a partir de `server/`, com ambiente Python isolado e sem preservar
segredos:

- `pytest -q`: **408 passed**, 1 warning de depreciação do `TestClient/httpx`;
- `ruff check .` e `ruff format --check .`: passaram;
- `python -m compileall -q app scripts`: passou;
- `bandit -q -ll -r app scripts`: passou sem achados; apenas warnings `nosec` existentes;
- `uv lock --check`: passou;
- testes de fixture, migração, catálogo, Print Screen, API, WebSocket, ciclo de
  vida e validação do harness incluídos na suíte.

### Android

Executado com JDK 21 e SDK Android locais:

- `:app:testDebugUnitTest`: passou;
- `:app:assembleDebug`: passou;
- `:app:assembleDebugAndroidTest`: passou;
- `:app:assembleRelease`: passou; APK release sem assinatura;
- `:app:lintDebug`: passou;
- build completo: `BUILD SUCCESSFUL`, 128 tarefas executadas.

O lint não reportou erro. Permanece um warning de depreciação pré-existente em
`QrScannerDialog.kt` (`LocalLifecycleOwner`).

### Integridade do checkout

- `HEAD` e `origin/master` permanecem em `301a930b060bb4c59cf372d49901cafcc5cc8046`;
- os 58 arquivos staged do baseline foram preservados;
- `stash@{0}` foi preservado;
- não foram criados commit, push, CI ou release;
- APKs/builds, bancos, screenshots, fixtures temporárias e segredos não foram
  adicionados ao Git;
- release continua unsigned e não distribuível sem keystore autorizada.

## Gate final HTTPS/WSS e emulador

Executado após o hardening final, com o emulador `Pixel_8` visível
(`emulator-5554`) e servidor temporário HTTPS/WSS:

- `OnboardingFlowInstrumentedTest`: 1/1 aprovado;
- `VisualGoldenInstrumentedTest`: 1/1 aprovado como smoke visual;
- `PairingFlowInstrumentedTest`: 1/1 aprovado, incluindo os oito controles,
  ACK, reconexão e persistência;
- XML agregado validado por `testcase@classname`, sem `failure`, `error` ou
  `skipped`;
- `android_https_wss_e2e=ok`;
- `port_released=true`;
- `temporary_state_removed=true`;
- nenhum fixture, screenshot ou banco temporário residual no emulador.

O harness usou `STREAMDECK_ACTION_MODE=recording`: não abriu Chrome, não alterou
volume e não emitiu Print Screen real. A leitura óptica física do QR e o smoke
de efeitos reais continuam fora da validação automatizada.
