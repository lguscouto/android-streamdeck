# Arquitetura do Android Stream Deck + Windows Server

## Visão geral

O sistema é uma aplicação Android que funciona como um painel remoto para um servidor executado no Windows. Os dois componentes comunicam-se somente na rede local durante o MVP. O Android exibe ações registradas e envia pedidos estruturados; o servidor valida, executa a ação correspondente e devolve eventos de estado.

```text
[Android Kotlin/Compose]
        |
        | OkHttp (WebSocket; mensagens JSON)
        v
[Windows Server: FastAPI + WebSocket]
        |
        +--> catálogo/validação de ações registradas
        +--> SQLite (configuração e histórico mínimo)
        +--> adaptadores internos de ações permitidas
```

## Matriz provisória de compatibilidade e decisões de ambiente

Esta matriz separa o inventário verificado no host das escolhas provisórias para o esqueleto. Ela **não confirma a compatibilidade final com o A10**: o aparelho não estava conectado, portanto modelo, API, tamanho e densidade ainda não foram medidos.

| Área | Fato verificado | Decisão provisória | Estado/limite |
| --- | --- | --- | --- |
| Java do Android | JBR OpenJDK `21.0.10` em `C:\Program Files\Android\Android Studio\jbr` | Usar JBR 21 | Fato do host; `java` não está no `PATH` |
| SDK e build Android | Plataformas `android-34`, `android-35`, `android-36.1`; build-tools `34.0.0`, `35.0.0`, `36.1.0`, `37.0.0` | `compileSdk 35`, `targetSdk 35`, build-tools `35.0.0` | Seleção provisória; não é validação de instalação no A10 |
| Dependências da toolchain | Cache local com AGP `8.2.1`, `8.7.2`, `8.8.2`; Gradle `8.10.2`, `8.13`, `9.4.1`; Kotlin Gradle plugin `2.0.21`; Compose UI `1.8.3`; Material3 `1.3.2`; Activity Compose `1.10.0` | Kotlin `2.0.21`, AGP `8.8.2`, Gradle `8.10.2` | Versões disponíveis no cache; a combinação ainda deve ser exercitada no build do projeto |
| A10 | Nenhum dispositivo/emulador conectado; `ro.build.version.sdk`, modelo, tamanho e densidade não medidos | `minSdk 26` somente para manter o esqueleto compilável | Deve ser confirmado/ajustado após obter a API real do A10, antes do release |
| Servidor | Python `3.14.6` e uv `0.11.21` encontrados | Python `3.14.6` com uv `0.11.21`, FastAPI/WebSocket, `127.0.0.1:8765` no desenvolvimento | Bind remoto exige código de pareamento e autenticação |
| Grade do painel | O perfil built-in atual usa 4 colunas × 3 linhas e dez controles, incluindo CPU e memória | A grade continua definida pelo snapshot `rows × columns`; o perfil inicial usa 3 × 4 | A ergonomia do A10 ainda requer validação física |

### Como revisar a decisão quando o A10 for conectado

1. Conectar e autorizar o A10, confirmar que ele aparece em `adb devices -l` e executar `adb shell getprop ro.product.model`.
2. Registrar os resultados reais de `adb shell getprop ro.build.version.sdk`, `adb shell wm size` e `adb shell wm density` em `docs/setup-android.md`.
3. Comparar a API medida com o `minSdk 26` provisório e ajustar o `minSdk` se a política de suporte exigir; a decisão final deve ser tomada com base na API real, não no nome “A10”.
4. Usar tamanho e densidade medidos para validar a grade 3 × 4 inicial, ajustando o default ou mantendo-o como configuração do usuário conforme o espaço disponível.
5. Exercitar a combinação Kotlin/AGP/Gradle/SDK em um build real e registrar o resultado. Só depois dessas verificações a matriz poderá deixar de ser provisória; este documento não afirma que um APK já foi criado.

## Cliente Android

- **Linguagem e UI:** Kotlin e Jetpack Compose.
- **Comunicação:** cliente OkHttp, com WebSocket para eventos de conexão e execução em tempo real. Requests HTTP de suporte, como health check ou catálogo, podem ser adicionados sem duplicar contratos.
- **Estado:** a UI reflete explicitamente desconectado, conectando, conectado, executando, concluído e erro. Cada `ack` ou `error` é associado ao `request_id` pendente antes de alterar o botão.
- **Modelo de ação:** o Android valida o `profile_snapshot`, renderiza `rows × columns` e envia apenas identificadores e revisão em `press`; a UI não monta comandos de sistema nem recebe payloads de execução.
- **Configuração:** endereço do servidor e parâmetros locais do painel são configuráveis pelo usuário, sem depender de descoberta automática no primeiro MVP.

## Onboarding e superfície Command Glow

O Android mantém o shell de pareamento existente e adiciona uma camada de
primeira execução controlada por `onboardingVersion`. A versão atual é `1`:
usuários sem credencial veem três páginas com voltar, próximo, pular e
finalização; instalações que já possuem credencial são marcadas como vistas sem
interromper a reconexão. Configurações oferece `Ver tutorial novamente`, sem
apagar credenciais ou preferências.

A grade usa vetores Compose/Material Icons, cores semânticas e bordas de accent
em vez de bitmaps dos mockups. O perfil inicial é 3 × 4, row-major, com dez
controles, incluindo CPU & Temp e Memória. O tile Spotify declara na
acessibilidade que atua sobre a sessão de mídia global; não há OAuth ou promessa
de exclusividade. Tema claro/escuro, redução de movimento, háptico e fonte
ampliada continuam sob as preferências existentes.

## Servidor Windows

- **Stack:** Python, FastAPI e WebSocket.
- **Persistência:** SQLite local para catálogo/configuração das ações, preferências mínimas e histórico estritamente necessário. O arquivo do banco é dado de runtime e deve permanecer fora do Git.
- **Contratos:** mensagens WebSocket e endpoints auxiliares devem usar esquemas explícitos, validar tipos, limites e identificadores, e retornar erros estruturados.
- **Execução:** cada ação é um adaptador registrado no servidor, com código próprio e parâmetros permitidos. O registry atual mantém allowlists fechadas para `hotkey`, `key`, `media`, `text`, `url`, `application` e `system_info`. `system_info` aceita somente `cpu` e `memory`, lê APIs Win32 internas e usa WMI de zona térmica ACPI apenas como fallback sem consulta recebida do cliente; essa leitura depende do firmware e não equivale necessariamente à temperatura do pacote da CPU. A aplicação é resolvida por catálogo interno: `chrome` → `chrome.exe`, sem caminho ou argumentos do cliente. `PRINTSCREEN` é mapeado para `VK_SNAPSHOT` (`0x2C`) com down/up. Spotify usa a sessão multimídia global. O modo de gravação do harness é opt-in e não emite efeitos no desktop; produção usa os adaptadores Windows reais.

O perfil built-in `essential-controls` é carregado de uma fixture versionada e
instalado uma única vez por banco, com marcador persistente e transação. A
migração não substitui um perfil personalizado nem reativa um perfil que o
usuário removeu. Revisões continuam sendo a fronteira de concorrência para
edições e snapshots.

## Rede local e autenticação

A operação remota exige autenticação e TLS. O fluxo recomendado não pede um código
estático: o tray/janela local emite uma sessão efêmera com senha aleatória de 128
bits ou QR versionado, validade de 10 minutos e uso único. O Android deriva o
`session_id`, faz o bootstrap HTTPS e valida a prova HMAC que vincula versão,
sessão, salt, expiração, IP, porta e identidade da CA. Somente depois instala a
CA restrita, mantendo a validação normal de hostname/SAN, e envia o `client_proof`
no claim. O `pairing_code` no claim permanece apenas para compatibilidade legada.

O Android envia o token somente no payload do `hello`, nunca na URL. Sessões sem
token ou com token inválido são fechadas antes da leitura do perfil. O aplicativo
mantém endpoint, token, CA PEM e identidade interna cifrados com AES-GCM por chave
do Android Keystore; a senha temporária não é persistida nem usada na reconexão.

Em bind remoto, o transporte é HTTPS/WSS e não há fallback para HTTP/WS. O estado
TLS fica fora do checkout, em `%LOCALAPPDATA%\AndroidStreamDeck\tls`, com CA
persistente, leaf renovável, SANs explícitos, validação de cadeia e DACL NTFS
restritiva no Windows. A CA privada não é publicada por mDNS. A descoberta mDNS
é opt-in e apenas anuncia metadados fechados (`transport=https`, `tls=required`,
pareamento exigido), sem token, código ou fingerprint. Ela não substitui o
endpoint manual, o pareamento ou o bootstrap de confiança.

No loopback de desenvolvimento controlado, o servidor pode continuar usando
HTTP/WS conforme `STREAMDECK_TLS_MODE=auto`; o cliente Android continua restrito
a HTTPS/WSS no fluxo normal.

O owner pode habilitar a administração de dispositivos com um
`STREAMDECK_ADMIN_CODE` separado: o inventário sanitizado e a revogação
idempotente não aceitam o código de pareamento. Sem esse valor, essas rotas ficam
desabilitadas. Tentativas inválidas de pareamento e administração são limitadas a
cinco por origem a cada 60 segundos. Nenhuma credencial deve ser armazenada no
repositório.

## Limite de segurança: sem shell command arbitrário

O servidor **não aceita, interpreta ou repassa comandos shell arbitrários** recebidos do Android. Em particular:

- não existe campo de protocolo como `command`, `cmd` ou `shell` que seja executado diretamente;
- entrada do cliente seleciona apenas uma ação de uma allowlist registrada no servidor;
- cada payload é validado contra o esquema da ação e rejeitado quando contém campos inesperados;
- ações que precisem interagir com o sistema usam adaptadores internos com argumentos construídos pelo código, nunca concatenação de strings para shell;
- identificadores desconhecidos, payloads inválidos e tentativas de incluir comandos devem gerar erro seguro e auditável, sem execução parcial.

Esse limite é parte do contrato da arquitetura e deve ser preservado em testes, documentação de API e revisões futuras. A inclusão de uma nova capacidade exige um novo adaptador explícito, seus testes e sua validação de segurança; não se deve criar um endpoint genérico de execução.

## Fluxo principal

1. O Android configura o endereço e abre o WebSocket.
2. O servidor autentica/valida a sessão e envia o snapshot do perfil selecionado.
3. O usuário toca em um botão da página ativa.
4. O cliente envia `press` com `request_id`, perfil, página, botão e revisão.
5. O servidor valida o envelope, a sessão, a revisão e a ação fechada do botão.
6. O adaptador habilitado devolve `ack` como `completed` ou `rejected`; o cliente
   atualiza o estado visual do botão.

## Evolução prevista

A arquitetura deixa espaço para perfis de painel, edição de layouts, mais adaptadores, autenticação forte e operação fora da rede local. Esses recursos não fazem parte do scaffold nem devem enfraquecer a regra de allowlist para facilitar uma implementação futura.
