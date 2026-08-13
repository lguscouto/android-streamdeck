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
  de accent, estados de execução e duas células vazias não interativas;
- perfil built-in `essential-controls`, `Controles essenciais`, com uma página
  `Principal` 3 × 4 e dez controles;
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
| 2,2 | CPU & Temp | `system_info/cpu` |
| 2,3 | Memória | `system_info/memory` |

As posições 0,3 e 1,3 permanecem vazias e não clicáveis.

Spotify usa a sessão multimídia global do Windows; não há OAuth nem garantia de
exclusividade. Print Screen coloca a captura no clipboard pelo comportamento do
Windows, mas o servidor não salva, transmite ou registra a imagem.

## Validação executada neste incremento

### Servidor

Executado a partir de `server/`, com ambiente Python isolado:

- `pytest -q`: **459 passed**, com um warning de depreciação do
  `TestClient/httpx`;
- `ruff check .` e `ruff format --check .`: passaram;
- `python -m compileall -q app scripts`: passou;
- `uv lock --check`: passou;
- leitura nativa no host: `CPU: 30% | N/A` e
  `RAM: 65% (10.9/31.7 GB)`; temperatura ACPI indisponível foi tratada como
  `N/A`;
- build PyInstaller e smoke: servidor/tray iniciaram, health/export/import
  passaram, a porta foi liberada e o estado temporário foi removido.

### Android

Executado com JDK 21 e SDK Android locais:

- `:app:testDebugUnitTest`, `:app:assembleDebug`,
  `:app:assembleDebugAndroidTest` e `:app:lintDebug`: passaram;
- APK debug: `android/app/build/outputs/apk/debug/app-debug.apk`
  (**42.979.173 bytes**);
- APK instrumentado:
  `android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk`
  (**454.019 bytes**);
- instalação incremental e lançamento no `Pixel_8` passaram, com
  `topResumedActivity=MainActivity` e nenhum `FATAL EXCEPTION` no logcat;
- E2E HTTPS/WSS no emulador: `android_https_wss_e2e=ok`, porta liberada e
  estado temporário removido;
- a instância anterior em `Y:\streamdeck` foi pausada somente durante o gate e
  restaurada automaticamente na mesma porta após a validação.

### Integridade do checkout

- `HEAD` permaneceu em `a3fa017134bcb31b54328be3e5ac8ad725d75f4d`;
- alterações staged preexistentes foram preservadas;
- não foram criados commit, push, CI ou release;
- APKs/builds, bancos, screenshots, estado temporário e segredos não foram
  adicionados ao Git;
- release continua unsigned e não distribuível sem keystore autorizada.

## Evidência histórica da Fase 11

A entrega original da Fase 11 executou o gate HTTPS/WSS no emulador `Pixel_8`
visível (`emulator-5554`) com o perfil de oito controles então vigente:

- `OnboardingFlowInstrumentedTest`: 1/1 aprovado;
- `VisualGoldenInstrumentedTest`: 1/1 aprovado como smoke visual;
- `PairingFlowInstrumentedTest`: 1/1 aprovado, com ACK, reconexão e
  persistência;
- XML agregado sem `failure`, `error` ou `skipped`;
- `android_https_wss_e2e=ok`, porta liberada e estado temporário removido.

O harness usou `STREAMDECK_ACTION_MODE=recording`: não abriu Chrome, não alterou
volume e não emitiu Print Screen real. A leitura óptica física do QR e o smoke
de efeitos reais continuam fora da validação automatizada.
