# Android Stream Deck

> Um painel Android local para acionar ações registradas do Windows com resposta visual, pareamento protegido e sem depender de nuvem.

## Controle seu Windows pelo Android

O Android Stream Deck transforma o telefone em um painel de controles rápidos para mídia, volume, Chrome e captura de tela. O aplicativo Android conversa com um servidor executado no Windows pela rede local; o servidor valida cada ação e a encaminha para um adaptador Windows explicitamente habilitado.

O projeto é voltado a quem quer atalhos físicos no celular, operação local e um limite de segurança claro — sem entregar ao telefone um executor genérico de shell, comandos ou caminhos.

## Por que usar

- **Controles rápidos:** ações frequentes ficam organizadas em uma grade de acesso direto.
- **Resposta no painel:** o Android mostra estados de conexão, execução, conclusão e erro.
- **Operação local:** não há sincronização em nuvem nem dependência de um serviço externo para o fluxo principal; a rede local tende a reduzir a latência do caminho de controle, embora a resposta real dependa da rede e do Windows.
- **Segurança por catálogo fechado:** o servidor só executa ações e aplicações registradas; entradas desconhecidas são rejeitadas.
- **Pareamento protegido:** o uso remoto combina sessão temporária, HTTPS/WSS, bootstrap de confiança e credencial protegida.
- **Personalização gradual:** perfis, páginas, layouts e revisões podem ser administrados pelo servidor.

## Principais características

| Área | O que está disponível |
| --- | --- |
| Aplicativo | Android nativo em Kotlin com Jetpack Compose e cliente OkHttp |
| Servidor | Python com FastAPI e WebSocket, executado no Windows |
| Persistência | SQLite local para perfis, configurações e histórico mínimo necessário |
| Painel inicial | Perfil `essential-controls` (`Controles essenciais`), grade 3 × 3, oito controles e uma célula vazia |
| Ações | Catálogos fechados para teclas, mídia, texto, URL e aplicações habilitadas |
| Mídia e volume | Play/Pause, próxima, mute, volume + e volume − via adaptadores Windows |
| Chrome | Aplicação selecionada por `app_id=chrome`, resolvida internamente como `chrome.exe` |
| Print Screen | Tecla Windows `PRINTSCREEN`/`VK_SNAPSHOT`; a captura permanece no clipboard do Windows |
| Perfis | Editor, páginas configuráveis, revisões e atualização otimista |
| Rede local | Pareamento temporário, QR opcional, HTTPS/WSS e validação de TLS/SAN para acesso remoto |
| Operação Windows | `streamdeck-tray.exe` para iniciar, parar e acompanhar o servidor |
| Entrega | Pacote portátil Windows x64, sem necessidade de Python ou `uv` no computador de destino |
| Limite explícito | Nenhum shell, comando, subprocesso ou caminho arbitrário fornecido pelo Android |

## Perfil inicial: Controles essenciais

Em uma instalação nova, o servidor instala de forma idempotente o perfil `essential-controls` (`Controles essenciais`). A página `Principal` usa uma grade 3 × 3; a nona célula é vazia e não interativa.

| Controle | Ação registrada |
| --- | --- |
| Play/Pause | `media/play_pause` |
| Próxima | `media/next` |
| Mute | `media/mute` |
| Spotify | `media/play_pause` na sessão de mídia global do Windows |
| Chrome | `application/chrome` |
| Volume + | `media/volume_up` |
| Volume − | `media/volume_down` |
| Print Screen | `key/PRINTSCREEN` |

O controle **Spotify** atua sobre a sessão de mídia global ativa do Windows. Ele não implementa OAuth e não promete exclusividade sobre o Spotify. O controle **Chrome** depende de o Chrome estar disponível no computador; o cliente não fornece executável, caminho nem argumentos.

## Como funciona

```text
Android Kotlin/Compose
        │
        ▼
Pareamento temporário e bootstrap de confiança
        │
        ▼
HTTPS/WSS na rede local
        │
        ▼
Servidor Windows Python/FastAPI/WebSocket
        │
        ├── valida envelope, perfil, revisão e ação fechada
        ├── persiste dados locais em SQLite
        └── chama o adaptador Windows correspondente
```

Fluxo de uso:

1. O Android inicia o pareamento pelo endereço do servidor ou pelo QR exibido localmente.
2. O servidor entrega uma sessão temporária e prova o material TLS antes do vínculo autenticado.
3. O Android mantém a credencial protegida e abre o WebSocket autenticado.
4. Ao tocar em um controle, o cliente envia somente identificadores, revisão e `request_id`.
5. O servidor valida a solicitação e executa o adaptador fechado, retornando `completed`, `rejected` ou erro sanitizado.

O transporte remoto do Android é HTTPS/WSS. O endpoint HTTP de saúde em loopback serve para verificar o processo local e não substitui o transporte autenticado da rede.

## Instalação rápida para usuário final

### Requisitos

- Windows 10 ou Windows 11 x64.
- Android 8.0/API 26 ou superior; a compatibilidade final ainda depende do dispositivo.
- Um pacote portátil Windows x64 contendo `streamdeck-server.exe` e `streamdeck-tray.exe`.
- Para um celular físico, computador e telefone na mesma rede privada.
- Para ações de áudio e mídia, uma sessão de mídia e os dispositivos correspondentes disponíveis no Windows.
- Para o emulador Android, o endereço especial do host e a configuração TLS correspondentes.

O pacote não é um instalador MSI. A pasta extraída deve permanecer intacta no local escolhido. O executável do pacote não é assinado digitalmente; o Windows pode exibir um alerta do SmartScreen. O APK Android não está incluído no ZIP do servidor: ele é uma entrega separada e, sem keystore autorizado, o APK release permanece unsigned.

### Como obter o pacote

Este repositório não fornece uma URL pública de download versionada. Não trate `server/dist` como uma página pública nem como um release publicado. Se você recebeu um pacote de uma fonte confiável, confirme sua origem e o manifesto/hash fornecido pelo operador antes de executá-lo.

Quando não houver um artefato distribuído, gere o pacote seguindo [Build e smoke do pacote Windows](#build-e-smoke-do-pacote-windows) na seção de desenvolvimento. O processo produz os dois executáveis em `server/dist/`; a montagem e a distribuição do arquivo portátil são etapas operacionais separadas.

### Início rápido: processo local e pareamento

1. Extraia a pasta do pacote em um local permanente, sem renomear os executáveis.
2. Execute `streamdeck-tray.exe` ou o `iniciar-tray.cmd` incluído no pacote validado.
3. No menu do ícone na bandeja, escolha **Iniciar servidor**.
4. Para verificar somente o processo local, confirme a saúde em:

   ```text
   http://127.0.0.1:8765/health
   ```

   A resposta esperada contém `status: ok`, o serviço `android-streamdeck-server` e `protocol_version: 0.1`.

A configuração padrão usa `127.0.0.1:8765` para desenvolvimento e diagnóstico local. Ela não é o caminho de pareamento do celular: a janela **Parear dispositivo** precisa de um bind remoto protegido, um IPv4 privado não-loopback e uma identidade TLS correspondente. Escolha um dos fluxos abaixo **antes** de selecionar **Parear dispositivo**:

- **Emulador Android:** use a configuração segura com `10.0.2.2` descrita em [Uso local e no emulador](#uso-local-e-no-emulador).
- **Celular físico:** use o IPv4 privado do Windows, a configuração TLS/SAN e a regra de firewall descritas em [Uso com celular na rede privada](#uso-com-celular-na-rede-privada).

Depois da configuração, a interface do tray oferece **Parear dispositivo**; porém, no checkout atual, conclua o pareamento pelo workaround manual abaixo, usando no Android o código e o endereço retornados pelo comando. Depois, abra o perfil **Controles essenciais**.

> **Limitação conhecida do checkout atual:** a janela de pareamento do tray acessa a rota local pelo IP privado exibido, enquanto o servidor aceita essa rota somente quando a origem é loopback. Um probe isolado reproduziu `403 LOCAL_ONLY` nessa combinação. Por isso, o pareamento automático pela janela do tray ainda não deve ser tratado como validado; use o workaround manual abaixo até que esse caminho seja corrigido no código.

O tray controla somente o processo que ele próprio iniciou. O banco SQLite, o estado TLS e os logs ficam fora da pasta do pacote, por padrão em `%LOCALAPPDATA%\AndroidStreamDeck`.

### Uso local e no emulador

Por padrão, o servidor executado diretamente escuta em `127.0.0.1:8765`. Esse modo é útil para verificar o processo e os endpoints locais, mas não oferece o endereço remoto exigido pela janela de pareamento.

No emulador Android padrão, o host Windows é acessado pelo endereço `10.0.2.2`. Em uma sessão do PowerShell aberta na pasta do pacote, configure o bind remoto antes de iniciar o tray:

```powershell
$env:STREAMDECK_HOST = "0.0.0.0"
$env:STREAMDECK_PORT = "8765"
$env:STREAMDECK_REQUIRE_AUTH = "true"
$env:STREAMDECK_TLS_MODE = "required"
$env:STREAMDECK_TLS_IDENTITIES = "10.0.2.2"
$env:STREAMDECK_PAIRING_SERVER_IP = "10.0.2.2"
$env:STREAMDECK_ADMIN_CODE = Read-Host "Código administrativo"
.\streamdeck-tray.exe
```

O certificado usado pelo fluxo seguro precisa conter `10.0.2.2` no SAN, e o endpoint do aplicativo deve usar HTTPS/WSS. Com o tray iniciado nessa sessão, escolha **Iniciar servidor** e use o workaround manual abaixo; não trate a janela **Parear dispositivo** como validada no checkout atual. A configuração detalhada de bootstrap TLS e do emulador está em [Fase 7 — transporte LAN seguro](docs/phase-7-delivery.md) e [Diagnóstico do ambiente Android e Python](docs/setup-android.md).

Para contornar a limitação atual da janela do tray, crie a sessão pelo endpoint local, mantendo `10.0.2.2` como nome TLS e redirecionando somente a conexão administrativa para loopback:

```powershell
$ca = Join-Path $env:LOCALAPPDATA 'AndroidStreamDeck\tls\ca-cert.pem'
$admin = Read-Host "Código administrativo"
$header = "X-StreamDeck-Admin-Code: $admin"
$pairing = $header | curl.exe --silent --show-error --cacert $ca `
  --resolve '10.0.2.2:8765:127.0.0.1' `
  --header '@-' `
  -X POST 'https://10.0.2.2:8765/api/v1/local/pairing-session' | ConvertFrom-Json
$pairing | Select-Object server_ip, port, pairing_code, qr_uri
```

Use no Android o `server_ip` e o `pairing_code` exibidos, ou o `qr_uri` quando o aplicativo oferecer leitura manual. A porta `8765` permanece a configuração interna do aplicativo. O parâmetro `--resolve` afeta apenas essa chamada local; o certificado continua sendo validado para `10.0.2.2`. O header é enviado pelo stdin do `curl.exe`, para não colocar o código administrativo na linha de comando.

## Uso com celular na rede privada

O computador e o telefone devem estar na mesma rede privada. Use o IPv4 privado real do Windows — por exemplo, `192.168.1.50` — e substitua o exemplo abaixo pelo endereço que sua máquina realmente possui. Não use um IP público, não encaminhe a porta no roteador e não exponha o servidor à internet.

Em uma janela do **PowerShell**, configure o bind remoto e o TLS antes de iniciar o tray ou o servidor:

```powershell
$env:STREAMDECK_HOST = "0.0.0.0"
$env:STREAMDECK_PORT = "8765"
$env:STREAMDECK_REQUIRE_AUTH = "true"
$env:STREAMDECK_TLS_MODE = "required"
$env:STREAMDECK_TLS_IDENTITIES = "192.168.1.50"
$env:STREAMDECK_PAIRING_SERVER_IP = "192.168.1.50"
$env:STREAMDECK_ADMIN_CODE = Read-Host "Código administrativo"
.\streamdeck-tray.exe
```

Se estiver executando a partir do checkout em vez do pacote, use `uv run --locked --no-sync streamdeck-tray` no lugar do executável. O código administrativo deve ter de 6 a 64 caracteres ASCII e não deve ser salvo no Git, em `.env`, em logs ou em uma captura de tela.

O valor de `STREAMDECK_TLS_IDENTITIES` deve corresponder exatamente ao endereço digitado no Android. O certificado precisa conter esse endereço no SAN. Depois de configurar, verifique a saúde remota em `https://<IP privado>:8765/health`. Como o servidor usa uma CA privada local, um navegador comum não confiará nela automaticamente. Não ignore o alerta nem desative a validação TLS: importe somente a CA pública `ca-cert.pem` como autoridade confiável no Windows, ou use o arquivo diretamente com `curl.exe`:

```powershell
$ca = Join-Path $env:LOCALAPPDATA 'AndroidStreamDeck\tls\ca-cert.pem'
curl.exe --cacert $ca https://192.168.1.50:8765/health
```

Mantenha `192.168.1.50` como exemplo apenas; substitua pelo IP real e confirme que ele aparece no SAN do certificado.

Com o tray iniciado, a sessão pode ser criada manualmente enquanto a limitação da janela de pareamento não for corrigida:

```powershell
$header = "X-StreamDeck-Admin-Code: $admin"
$pairing = $header | curl.exe --silent --show-error --cacert $ca `
  --resolve '192.168.1.50:8765:127.0.0.1' `
  --header '@-' `
  -X POST 'https://192.168.1.50:8765/api/v1/local/pairing-session' | ConvertFrom-Json
$pairing | Select-Object server_ip, port, pairing_code, qr_uri
```

Substitua o IP pelo endereço real. No Android, use os dados exibidos para concluir o pareamento manual.

### Firewall do Windows

A regra de entrada é manual, limitada a TCP/8765 e ao perfil **Private**. Ela não é criada automaticamente pelo servidor. Em um checkout de desenvolvimento, abra um PowerShell elevado na pasta `server/` e use:

```powershell
.\scripts\windows-firewall.ps1 -Action Install -Port 8765
```

Para remover a regra:

```powershell
.\scripts\windows-firewall.ps1 -Action Remove -Port 8765
```

No pacote portátil, use as configurações do Firewall do Windows para criar a mesma regra, restrita ao perfil **Private**. Não selecione **Public** e não publique a porta na internet.

## Segurança e privacidade

- **Catálogo fechado:** o servidor mantém uma lista de permissões para tipos e parâmetros; o Android escolhe somente identificadores de ações existentes.
- **Sem execução arbitrária:** não há shell, `command`, `cmd`, subprocesso arbitrário, caminho livre ou comando fornecido pelo cliente. Uma aplicação é resolvida por catálogo interno; atualmente, `chrome` aponta para `chrome.exe` sem argumentos do cliente.
- **Pareamento efêmero:** a sessão recomendada usa senha aleatória ou QR versionado, expira em 10 minutos e só pode ser consumida uma vez.
- **Transporte autenticado:** binds remotos exigem autenticação e TLS; o Android valida a prova HMAC/HKDF do bootstrap antes de confiar na CA restrita e mantém a validação de hostname/SAN.
- **Credenciais protegidas:** o token, o endpoint e a CA usados pelo Android são armazenados de forma cifrada pelo Android Keystore; o servidor mantém o token persistido somente como hash.
- **CA e estado fora do Git:** chaves privadas, certificados, banco, logs, tokens e códigos ficam no estado de runtime, por padrão em `%LOCALAPPDATA%\AndroidStreamDeck`, e não dentro do pacote ou do checkout.
- **Revogação e limitação:** o servidor oferece revogação de dispositivos e invalida sessões WebSocket afetadas. Pareamento, administração e handshake WebSocket têm rate limit por origem.
- **Mensagens sanitizadas:** respostas e logs não devem expor token, senha, hash, CA, caminho local, SQL ou traceback ao cliente.
- **Dados locais:** não há nuvem no fluxo principal. O servidor não salva, transmite nem registra a imagem produzida pelo Print Screen; o comportamento do Windows coloca a captura no clipboard local.

Detalhes dos contratos, da autenticação e das fronteiras de segurança estão em [Arquitetura](docs/architecture.md), [README do servidor](server/README.md) e [Fase 7 — transporte LAN seguro](docs/phase-7-delivery.md).

## Limitações conhecidas

- O pacote atual é destinado a **Windows 10/11 x64**. Não há promessa de compatibilidade ampla com outros sistemas operacionais.
- O pacote Windows é portátil e **não é MSI**. A pasta deve permanecer no local escolhido.
- Os executáveis Windows não têm assinatura digital; o SmartScreen pode solicitar confirmação.
- O **APK release é unsigned** quando não existe um keystore externo autorizado. Ele não é instalável nem distribuível como está; o APK debug serve apenas ao desenvolvimento. Não há um APK release assinado publicado por este repositório.
- Configuração de bind remoto, certificado/SAN e firewall é manual. O fluxo seguro não deve ser substituído por HTTP/WS sem TLS na rede.
- Spotify usa a sessão de mídia global do Windows; o resultado depende do player e da sessão ativa e não é exclusivo do Spotify.
- Play/Pause, próxima, mute e volume dependem dos dispositivos, da sessão de mídia e do estado do Windows.
- Chrome depende de estar disponível no computador hospedeiro.
- Os smokes automatizados não substituem a validação de efeitos na sessão Windows real. A matriz atual de evidências está resumida em [Status atual](#status-atual).
- A janela de pareamento do tray ainda não foi validada ponta a ponta no bind privado; a rota local rejeita origens não-loopback com `403 LOCAL_ONLY`. O workaround manual documentado acima mantém a chamada administrativa em loopback.
- A validação registrada foi feita no emulador `Pixel_8`; o Galaxy A10 físico ainda não foi conectado e não foi validado.

## Desenvolvimento

### Estrutura do repositório

```text
android-streamdeck/
├── android/    # aplicativo Android Kotlin/Compose
├── server/     # servidor Python/FastAPI/WebSocket e tray Windows
├── shared/     # contratos, schemas e fixtures compartilhados
├── docs/       # arquitetura, setup e relatórios técnicos
└── .github/    # gates de CI
```

### Preparar e executar o servidor

Na raiz do repositório, com Python compatível (`>=3.11,<3.15`) e `uv` instalados:

```bash
cd server
uv sync --locked --all-groups
uv run --locked --no-sync streamdeck-server
```

Na raiz do repositório, o modo fonte usa `server/data/streamdeck.sqlite3`, ignorado pelo Git; depois de entrar em `server/`, o caminho relativo é `data/streamdeck.sqlite3`. O comando do tray é:

```bash
uv run --locked --no-sync streamdeck-tray
```

Para detalhes de ambiente, configuração, endpoints HTTP/WebSocket e pareamento, consulte [README do servidor](server/README.md).

### Gates do servidor

Execute a partir de `server/`:

```bash
uv run --locked --no-sync pytest -q
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv run --locked --no-sync python -m compileall -q app scripts
uv run --locked --no-sync bandit -q -ll -r app scripts
uv lock --check
```

### Build e smoke do pacote Windows

Com as dependências do grupo de desenvolvimento instaladas, execute a partir de `server/`:

```bash
uv run --locked --group dev python scripts/build_windows.py
uv run --locked --group dev python scripts/smoke_windows_bundle.py
uv run --locked --group dev python -m scripts.release_manifest
```

O build usa PyInstaller e gera `dist/streamdeck-server.exe` e `dist/streamdeck-tray.exe`. O smoke verifica health, export/import de perfil, encerramento dos processos, liberação da porta e remoção do estado temporário. O manifesto registra os artefatos, tamanhos, SHA-256 e estado de assinatura sem incluir segredos.

Para validar o transporte seguro e a integração com o emulador, use estado temporário e os pré-requisitos descritos na documentação da Fase 7:

```bash
uv run --locked --no-sync python scripts/phase7_tls_smoke.py
uv run --locked --no-sync python scripts/phase7_android_e2e.py
```

Esses testes de smoke exigem configuração adicional e um emulador Android conectado; não são necessários para o início rápido do usuário final.

### Build e validação Android

Configure um JDK/JBR 17 ou superior e o SDK Android local. O projeto usa Kotlin/Compose, `compileSdk 35`, `targetSdk 35` e `minSdk 26`; a compatibilidade física deve ser validada no dispositivo real antes de qualquer distribuição.

A partir de `android/`:

```bash
./gradlew.bat :app:testDebugUnitTest :app:assembleDebug \
  :app:assembleDebugAndroidTest :app:lintDebug --console=plain --no-daemon
./gradlew.bat :app:assembleRelease
./gradlew.bat :app:printReleaseSigningStatus
```

Sem um arquivo `release-signing.properties` completo ou sem as variáveis `STREAMDECK_*` correspondentes, a saída esperada é `RELEASE_SIGNING=unsigned`. Não use o keystore de debug como identidade de distribuição.

Os smokes HTTPS/WSS e o E2E no emulador estão documentados em [Fase 7 — validação](docs/phase-7-delivery.md) e no [relatório da Fase 11](docs/phase-11-delivery.md). Eles usam estado temporário; efeitos reais no desktop e a leitura física do QR continuam sendo validações separadas.

### Não versionar segredos nem artefatos

Não adicione ao Git:

- tokens, senhas, códigos de pareamento ou arquivos `.env`;
- chaves privadas, CA, certificados de runtime, `*.jks`, `*.keystore`, `*.p12` ou `*.pfx`;
- bancos SQLite, logs e dados em `%LOCALAPPDATA%\AndroidStreamDeck`;
- APKs, executáveis, diretórios `dist/` ou `build/` gerados localmente;
- `release-signing.properties`, `local.properties` ou qualquer configuração de assinatura.

## Troubleshooting rápido

| Sintoma | Verificações |
| --- | --- |
| `/health` não responde | Confirme **Iniciar servidor**, a porta `8765` e se outro processo não a está ocupando. |
| O celular não encontra o Windows | Confirme o IP privado, a mesma rede e a regra TCP no perfil **Private**; não use o perfil **Public**. |
| Erro de certificado | O endereço usado no Android precisa aparecer em `STREAMDECK_TLS_IDENTITIES` e no SAN do certificado. Gere uma nova sessão de pareamento após corrigir a configuração. |
| Sessão de pareamento recusada | Gere uma nova sessão; a senha expira em 10 minutos e tem uso único. Não reutilize uma sessão consumida. |
| Chrome não abre | Verifique se o Chrome está instalado e disponível no host Windows; o servidor não aceita caminho alternativo fornecido pelo cliente. |
| Mídia, Spotify ou volume não respondem | Verifique a sessão de mídia, o player ativo e o dispositivo de áudio do Windows. |

## Documentação técnica

- [Arquitetura do sistema](docs/architecture.md)
- [Diagnóstico e setup Android/Python](docs/setup-android.md)
- [README do servidor, API e operação Windows](server/README.md)
- [Fase 7 — transporte LAN seguro e gestão de dispositivos](docs/phase-7-delivery.md)
- [Fase 8 — release verificável](docs/phase-8-delivery.md)
- [Fase 9 — CI e hardening](docs/phase-9-delivery.md)
- [Fase 11 — onboarding e controles essenciais](docs/phase-11-delivery.md)
- [Workflow de gates](.github/workflows/gates.yml)

## Status atual

| Estado | Resumo |
| --- | --- |
| Disponível no checkout | Aplicativo Android com onboarding e perfil `essential-controls` (`Controles essenciais`); servidor Windows com FastAPI/WebSocket, SQLite, tray, editor de perfis e adaptadores fechados. |
| Segurança entregue | Pareamento temporário, HTTPS/WSS remoto, CA privada, proteção de credenciais, revogação, rate limit e respostas sanitizadas. |
| Empacotamento | Build reproduzível do pacote portátil Windows x64 e smoke do pacote; o processo não cria um instalador MSI. |
| Validação registrada | Gates de servidor, build Android, pacote e E2E HTTPS/WSS no `Pixel_8` estão registrados nos relatórios técnicos. |
| Efeitos Windows observados | Em uma sessão Windows real, volume +/−, mute, foco/execução do Chrome e Print Screen no clipboard foram confirmados. |
| Efeitos de mídia | Play/Pause, Próxima e Spotify foram despachados pelo protocolo, mas a semântica não foi confirmada porque não havia sessão de mídia global ativa. |
| Pareamento pelo tray | A sessão segura e o protocolo foram validados no harness; a janela do tray no bind privado permanece pendente por causa da restrição `LOCAL_ONLY`. |
| Validação ainda pendente | Leitura óptica física do QR, validação no Galaxy A10 físico e confirmação semântica das ações de mídia. |
| Entrega ainda pendente | Keystore autorizado para assinar o APK release e distribuição pública verificável. |

O histórico detalhado e os resultados de cada entrega permanecem nos [relatórios técnicos](#documentação-técnica), sem repetir aqui o diário completo das fases.
