# Diagnóstico do ambiente Android e Python

## Escopo e estado da inspeção

Este documento registra o diagnóstico real do host usado para o projeto. O
baseline Android e o cliente autenticado da Fase 2 já foram compilados; o fluxo
foi exercitado no emulador `Pixel_8`. O A10 físico ainda não foi validado.

## Ferramentas encontradas

| Componente | Resultado verificado |
| --- | --- |
| Host | Windows `10.0.26200` (o comando `ver` exibiu a build completa `10.0.26200.8973`) |
| JDK usado pelo Android Studio (JBR) | `openjdk version "21.0.10" 2026-01-20` |
| Caminho do JDK | `C:\Program Files\Android\Android Studio\jbr\bin\java.exe` |
| Executável do Android Studio | `C:\Program Files\Android\Android Studio\bin\studio64.exe` |
| Android SDK | `C:\Users\gustavo\AppData\Local\Android\Sdk` |
| ADB | `C:\Users\gustavo\AppData\Local\Android\Sdk\platform-tools\adb.exe` |
| Versão do ADB | `1.0.41` / `37.0.0-14910828` |
| Python | `3.14.6` (encontrado via `python3`) |
| uv | `0.11.21` |
| `java` no PATH | Não encontrado; o caminho absoluto do JBR funciona |
| `adb` no PATH | Não encontrado; o caminho absoluto do SDK funciona |

### Plataformas do SDK disponíveis

- `android-34`
- `android-35`
- `android-36.1`

### Build-tools disponíveis

- `34.0.0`
- `35.0.0`
- `36.1.0`
- `37.0.0`

### Dependências disponíveis no cache local do Gradle

Os artefatos abaixo foram encontrados no cache local; a presença no cache não equivale à validação de um build deste projeto:

- Android Gradle Plugin (AGP): `8.2.1`, `8.7.2`, `8.8.2`;
- distribuições Gradle: `8.10.2`, `8.13`, `9.4.1`;
- Kotlin Gradle plugin: `2.0.21`;
- Compose UI: `1.8.3`;
- Material3: `1.3.2`;
- Activity Compose: `1.10.0`.

## Estado do ADB e do dispositivo

O AVD `Pixel_8` está conectado como `emulator-5554` e respondeu com os
valores reais abaixo:

- modelo: `sdk_gphone16k_x86_64`;
- API: `37`;
- resolução: `1080x2400`;
- densidade: `420`.

O A10 continua não identificado e não medido.

## Como revisar a decisão quando o A10 for conectado

1. Conectar o A10 por USB, habilitar a depuração USB e autorizar a chave RSA no aparelho; ou iniciar um emulador Android para validar o fluxo de ferramentas.
2. Confirmar que o destino autorizado aparece em `adb devices -l`.
3. Repetir `adb shell getprop ro.product.model`, `adb shell getprop ro.build.version.sdk`, `adb shell wm size` e `adb shell wm density`, registrando os valores reais neste documento e na matriz de `docs/architecture.md`.
4. Comparar a API medida com o `minSdk 26` provisório e ajustar o `minSdk` conforme a política de suporte; não deduzir a API a partir do nome “A10”.
5. Usar tamanho e densidade medidos para validar a grade inicial de 3 colunas x 5 linhas e ajustar o default configurável se necessário.
6. A combinação Kotlin `2.0.21`, AGP `8.8.2`, Gradle `8.10.2`, `compileSdk 35`, `targetSdk 35` e build-tools `35.0.0` foi exercitada em builds reais de debug e release. Isso não substitui a validação física de compatibilidade no A10.

Até essa revisão, o `minSdk 26` é apenas uma escolha provisória para o esqueleto compilável e não uma afirmação de compatibilidade final com o A10.

## Comandos reproduzíveis — PowerShell (caminhos nativos)

Executar em uma sessão do PowerShell. As variáveis apontam explicitamente para o JBR, o SDK e o ADB encontrados nesta inspeção:

```powershell
$jbr = 'C:\Program Files\Android\Android Studio\jbr\bin\java.exe'
$sdk = 'C:\Users\gustavo\AppData\Local\Android\Sdk'
$adb = Join-Path $sdk 'platform-tools\adb.exe'

# Host, JDK e Android Studio
ver
& $jbr -version
Test-Path 'C:\Program Files\Android\Android Studio\bin\studio64.exe'

# Plataformas e build-tools instaladas
Get-ChildItem (Join-Path $sdk 'platforms') -Directory | Select-Object -ExpandProperty Name
Get-ChildItem (Join-Path $sdk 'build-tools') -Directory | Select-Object -ExpandProperty Name

# ADB e destinos conectados
& $adb version
& $adb devices -l

# Só produzirão dados quando houver dispositivo ou emulador autorizado
& $adb shell getprop ro.product.model
& $adb shell getprop ro.build.version.sdk
& $adb shell wm size
& $adb shell wm density

# Python, uv e presença de java/adb no PATH
python3 --version
uv --version
Get-Command java, adb -ErrorAction SilentlyContinue
```

Enquanto não houver destino conectado, os quatro comandos `adb shell` terminam com `adb.exe: no devices/emulators found`; isso é um bloqueio de conexão, não um valor de modelo/API/tamanho/densidade.

## Comandos reproduzíveis — MSYS/Git Bash

Os mesmos caminhos podem ser usados em formato MSYS. O `java.exe` e o `adb.exe` devem ser chamados pelos caminhos absolutos enquanto não estiverem no PATH:

```bash
JBR='/c/Program Files/Android/Android Studio/jbr/bin/java.exe'
SDK='/c/Users/gustavo/AppData/Local/Android/Sdk'
ADB="$SDK/platform-tools/adb.exe"

# Host, JDK e Android Studio
cmd.exe /c ver
"$JBR" -version
test -f '/c/Program Files/Android/Android Studio/bin/studio64.exe' && \
  printf '%s\n' 'Android Studio encontrado'

# Plataformas e build-tools instaladas
for dir in "$SDK"/platforms/android-*; do
  test -d "$dir" && basename "$dir"
done | sort -V
for dir in "$SDK"/build-tools/*; do
  test -d "$dir" && basename "$dir"
done | sort -V

# ADB e destinos conectados
"$ADB" version
"$ADB" devices -l

# Só produzirão dados quando houver dispositivo ou emulador autorizado
"$ADB" shell getprop ro.product.model
"$ADB" shell getprop ro.build.version.sdk
"$ADB" shell wm size
"$ADB" shell wm density

# Python, uv e presença de java/adb no PATH
python3 --version
uv --version
command -v java || true
command -v adb || true
```

## Matriz provisória de compatibilidade e decisões de ambiente

A matriz abaixo é a referência inicial para o desenvolvimento. “Fato verificado” descreve o host ou a inspeção realizada; “decisão provisória” descreve uma escolha de projeto que ainda pode ser revisada. A ausência de um destino conectado impede qualquer afirmação de compatibilidade final com o A10.

| Área | Fato verificado | Decisão provisória |
| --- | --- | --- |
| Java do Android | JBR OpenJDK `21.0.10` em `C:\Program Files\Android\Android Studio\jbr` | Usar JBR 21; chamar o executável por caminho absoluto enquanto `java` não estiver no `PATH` |
| Android SDK | Plataformas `android-34`, `android-35`, `android-36.1` disponíveis | `compileSdk 35`, `targetSdk 35` |
| Build Android | Build-tools `34.0.0`, `35.0.0`, `36.1.0`, `37.0.0` disponíveis | Usar build-tools `35.0.0` |
| Toolchain em cache | AGP `8.2.1`, `8.7.2`, `8.8.2`; Gradle `8.10.2`, `8.13`, `9.4.1`; Kotlin Gradle plugin `2.0.21`; Compose UI `1.8.3`; Material3 `1.3.2`; Activity Compose `1.10.0` disponíveis | Usar Kotlin `2.0.21`, AGP `8.8.2` e Gradle `8.10.2`; exercitar a combinação em build real antes de tratá-la como validada |
| A10 | Sem dispositivo/emulador conectado; modelo, API, tamanho e densidade **não medidos** | `minSdk 26` apenas para o esqueleto compilável; confirmar ou ajustar antes do release |
| Servidor | Python `3.14.6` e uv `0.11.21` encontrados | Python `3.14.6` com uv `0.11.21`, FastAPI/WebSocket, host `127.0.0.1` e porta `8765` no desenvolvimento; testar LAN antes de mudar o host |
| Grade do painel | Tamanho e densidade do A10 ainda não medidos | Default configurável de 3 colunas x 5 linhas |

## Destino oficial de validação Android

A validação funcional e visual desta primeira implementação será feita no AVD **`Pixel_8`**, que está cadastrado no Android Emulator local. O A10 continua sendo o aparelho-alvo de compatibilidade futura, mas não será usado como bloqueio para o desenvolvimento nem será declarado validado sem uma execução posterior.

## Estado verificado do AVD de validação

O AVD foi iniciado e respondeu a `adb` com os seguintes valores reais:

- destino: `emulator-5554`;
- modelo reportado: `sdk_gphone16k_x86_64`;
- API: `37`;
- resolução física: `1080x2400`;
- densidade: `420`.

Esses dados descrevem o emulador Pixel_8 e não o Galaxy A10.

Para iniciar o destino de teste:

```bash
SDK='/c/Users/gustavo/AppData/Local/Android/Sdk'
"$SDK/emulator/emulator.exe" -avd Pixel_8 -no-snapshot-load
```

Depois, aguardar `sys.boot_completed=1`, confirmar `adb devices` e repetir a validação no APK final. A automação da interface nativa Compose usa ADB/UiAutomator; o fluxo CDP de WebView não se aplica a este app nativo.

## Smoke funcional da Fase 2

A validação final usou UiAutomator instrumentado no `Pixel_8`, e não injeção de
teclas ADB, para preencher o campo Compose de forma confiável. Um servidor
efêmero em `0.0.0.0:8765` recebeu um código aleatório apenas em memória; o código
foi passado ao runner do teste, sem ser gravado no projeto nem em relatórios.

O teste verificou o fluxo completo:

1. pareamento HTTP;
2. `hello` WebSocket autenticado;
3. estados visíveis `Conectado`, `Servidor autenticado` e
   `Perfil sincronizado na revisão 1`;
4. três valores de preferências no envelope cifrado `v1:`, sem token em texto
   claro;
5. reinício da atividade e reconexão sem reenviar o código.

O relatório do AVD registrou dois testes e zero falhas. O servidor, banco
SQLite temporário e dados do aplicativo foram removidos ao fim do smoke; a porta
`8765` não permaneceu em escuta. Consulte
[`phase-2-delivery.md`](phase-2-delivery.md) para os comandos e artefatos finais.

## Recomendação provisória para o desenvolvimento

- Usar explicitamente o JBR 21 do Android Studio em comandos e configurações locais. O caminho confirmado é `C:\Program Files\Android\Android Studio\jbr\bin\java.exe` (ou `/c/Program Files/Android/Android Studio/jbr/bin/java.exe` no MSYS).
- Usar o ADB pelo caminho absoluto confirmado enquanto ele não for adicionado ao `PATH`: `C:\Users\gustavo\AppData\Local\Android\Sdk\platform-tools\adb.exe`.
- Manter o servidor em `127.0.0.1:8765` durante o desenvolvimento local; para testar o Android em LAN/emulador, usar bind remoto somente com `STREAMDECK_PAIRING_CODE` e `STREAMDECK_REQUIRE_AUTH=auto`.
- Não registrar modelo, API, tamanho ou densidade do A10 como se fossem conhecidos. Esses valores só podem ser preenchidos após uma consulta bem-sucedida ao dispositivo.
