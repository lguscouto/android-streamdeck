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
| Grade do painel | Dimensões e densidade do A10 ainda não medidas | Grade inicial configurável de 3 colunas x 5 linhas | Default provisório; revisar quando houver medidas reais do aparelho |

### Como revisar a decisão quando o A10 for conectado

1. Conectar e autorizar o A10, confirmar que ele aparece em `adb devices -l` e executar `adb shell getprop ro.product.model`.
2. Registrar os resultados reais de `adb shell getprop ro.build.version.sdk`, `adb shell wm size` e `adb shell wm density` em `docs/setup-android.md`.
3. Comparar a API medida com o `minSdk 26` provisório e ajustar o `minSdk` se a política de suporte exigir; a decisão final deve ser tomada com base na API real, não no nome “A10”.
4. Usar tamanho e densidade medidos para validar a grade 3x5, ajustando o default ou mantendo-o como configuração do usuário conforme o espaço disponível.
5. Exercitar a combinação Kotlin/AGP/Gradle/SDK em um build real e registrar o resultado. Só depois dessas verificações a matriz poderá deixar de ser provisória; este documento não afirma que um APK já foi criado.

## Cliente Android

- **Linguagem e UI:** Kotlin e Jetpack Compose.
- **Comunicação:** cliente OkHttp, com WebSocket para eventos de conexão e execução em tempo real. Requests HTTP de suporte, como health check ou catálogo, podem ser adicionados sem duplicar contratos.
- **Estado:** a UI deve refletir explicitamente desconectado, conectando, conectado, executando, sucesso e erro.
- **Modelo de ação:** cada botão referencia um identificador de ação conhecido e um payload tipado/validado; a UI não monta comandos de sistema.
- **Configuração:** endereço do servidor e parâmetros locais do painel são configuráveis pelo usuário, sem depender de descoberta automática no primeiro MVP.

## Servidor Windows

- **Stack:** Python, FastAPI e WebSocket.
- **Persistência:** SQLite local para catálogo/configuração das ações, preferências mínimas e histórico estritamente necessário. O arquivo do banco é dado de runtime e deve permanecer fora do Git.
- **Contratos:** mensagens WebSocket e endpoints auxiliares devem usar esquemas explícitos, validar tipos, limites e identificadores, e retornar erros estruturados.
- **Execução:** cada ação é um adaptador registrado no servidor, com código próprio e parâmetros permitidos. O servidor devolve confirmação de recebimento e atualizações de progresso/resultado quando aplicável.

## Rede local e autenticação

O servidor usa `127.0.0.1` por padrão. Para permitir conexão do Android em outra
interface, é obrigatório configurar `STREAMDECK_PAIRING_CODE`; a configuração
ativa autenticação do WebSocket automaticamente. O endpoint HTTP de pareamento
recebe o código fora do repositório e emite um token opaco aleatório. O banco
persiste somente o hash SHA-256 desse token e substitui o token anterior quando
o mesmo `client_id` é pareado novamente.

O Android envia o token somente no payload do `hello`, nunca na URL. Sessões sem
token ou com token inválido são fechadas antes da leitura do perfil. O aplicativo
mantém o token criptografado com AES-GCM por chave do Android Keystore e só o usa
para o endpoint normalizado que emitiu o pareamento. O MVP usa HTTP/WS em rede
local confiável e não deve ser exposto à internet; TLS/mTLS, rotação administrativa
e descoberta segura são hardening posterior. Nenhuma credencial deve ser
armazenada no repositório.

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
2. O servidor autentica/valida a sessão conforme o mecanismo adotado e envia o catálogo de ações permitidas.
3. O usuário toca em um botão.
4. O cliente envia um evento estruturado com `action_id`, identificador da solicitação e payload validado.
5. O servidor valida o envelope e o schema da ação, registra o início e executa somente o adaptador correspondente.
6. Eventos de estado retornam pelo WebSocket; o Android atualiza o botão e apresenta sucesso ou erro.

## Evolução prevista

A arquitetura deixa espaço para perfis de painel, edição de layouts, mais adaptadores, autenticação forte e operação fora da rede local. Esses recursos não fazem parte do scaffold nem devem enfraquecer a regra de allowlist para facilitar uma implementação futura.
