# Servidor Android Stream Deck

Servidor FastAPI/WebSocket local para o Android Stream Deck.

## Executar no Windows

A partir deste diretório:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync streamdeck-server
```

Padrões:

- host: `127.0.0.1`
- porta: `8765`
- banco no modo fonte: `server/data/streamdeck.sqlite3`; no bundle:
  `%LOCALAPPDATA%\AndroidStreamDeck\streamdeck.sqlite3`
- estado TLS no Windows: `%LOCALAPPDATA%\AndroidStreamDeck\tls`
- pareamento: desabilitado no modo loopback sem código configurado
- TLS: `auto`; loopback pode usar HTTP/WS no desenvolvimento controlado, mas
  bind remoto é promovido para HTTPS/WSS obrigatoriamente

O endpoint de saúde padrão é `http://127.0.0.1:8765/health`.

O arquivo `.env.example` é apenas documentação e não é carregado automaticamente.
Não grave códigos de pareamento, tokens ou outras credenciais no repositório.

## Operação no Windows — Fases 6 e 7

### Tray opcional

O tray não inicia automaticamente o servidor por padrão. Ele mostra o estado do
processo que ele próprio controla e oferece `Iniciar servidor`, `Parar servidor`
e `Sair`:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync streamdeck-tray
```

O tray usa um comando fixo (`python -m app.runner` no modo fonte ou
`streamdeck-server.exe` no bundle), sem `shell`, comandos fornecidos pelo usuário
ou caminho executável livre. Ao sair, ele encerra somente o processo criado por
ele.

### Descoberta local opcional

A descoberta mDNS/DNS-SD fica desativada por padrão. Para anunciar o servidor na
rede local, é necessário configurar explicitamente um bind remoto autenticado:

```text
STREAMDECK_HOST=192.168.x.x
STREAMDECK_PORT=8765
STREAMDECK_DISCOVERY_ENABLED=true
STREAMDECK_DISCOVERY_NAME=Android Stream Deck
```

O tipo anunciado é `_android-streamdeck._tcp.local.`. O anúncio contém apenas
versão do protocolo, porta, `requires_pairing=true`, `transport=https` e
`tls=required`; não contém código de pareamento, token, caminho, banco ou
snapshot. O primeiro pareamento continua funcionando por endereço digitado
manualmente, sem depender do mDNS. A configuração de descoberta é rejeitada em
loopback, wildcard, hostname, IP público ou rede reservada; use somente um IPv4
RFC1918 concreto (`10/8`, `172.16/12` ou `192.168/16`).

### Bundle Windows e smoke

A partir de `server/`, com as dependências de desenvolvimento instaladas:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --group dev python scripts/build_windows.py
env -u PYTHONPATH -u VIRTUAL_ENV uv run --group dev python scripts/smoke_windows_bundle.py
```

O build gera, fora do Git, `dist/streamdeck-server.exe` e
`dist/streamdeck-tray.exe`, empacotando `shared/protocol` e `shared/fixtures`
(schemas e fixtures públicos; banco, CA, chaves, tokens, logs e configurações
mutáveis permanecem em `%LOCALAPPDATA%\AndroidStreamDeck` quando congelado).
O smoke usa banco temporário e porta loopback efêmera, consulta `/health`, executa
um export seguido de um import de perfil válido pelo executável congelado,
encerra a árvore do processo e verifica porta liberada e remoção do diretório
temporário.

Para usar um pacote já gerado em outro computador Windows x64, extraia a pasta
`AndroidStreamDeck-Windows-x64` e execute `streamdeck-tray.exe`. No menu do ícone
da bandeja, escolha `Iniciar servidor`; para configurar o pareamento, escolha
`Parear dispositivo`. O computador de destino não precisa ter Python, uv ou o
repositório instalado. O executável do servidor também pode ser iniciado
diretamente para uso local em `127.0.0.1:8765`.

O pacote é portátil, mas não é um instalador MSI: a pasta deve permanecer no
local escolhido pelo usuário. O banco, certificados TLS e logs ficam fora da
pasta do pacote, em `%LOCALAPPDATA%\AndroidStreamDeck`. Para uso pelo Android
em uma rede local, o bind remoto, as identidades TLS e a regra de firewall
privada continuam sendo configurados explicitamente; não exponha a porta em
uma rede pública ou na internet.

Manifesto de release determinístico:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --group dev python -m scripts.release_manifest
```

### Autostart reversível

O script não é executado automaticamente. Em PowerShell, depois de escolher um
bundle local confiável:

```powershell
.\scripts\windows-autostart.ps1 -Action Install -ExecutablePath 'C:\caminho\streamdeck-tray.exe'
.\scripts\windows-autostart.ps1 -Action Remove
```

A tarefa usa o usuário interativo atual e `RunLevel Limited`; a remoção usa o
nome fixo `Android Stream Deck Tray`.

### Firewall restrito à rede privada

A regra também é manual, exige PowerShell elevado e nunca é criada pelo servidor:

```powershell
.\scripts\windows-firewall.ps1 -Action Install -Port 8765
.\scripts\windows-firewall.ps1 -Action Remove -Port 8765
```

A regra permite somente TCP na porta escolhida e no perfil `Private`. Não use o
perfil `Public` e não exponha a porta à internet. O bind remoto continua exigindo
código de pareamento e autenticação.

## Expor para o Android na rede local

O bind remoto exige autenticação e TLS. Configure um código administrativo e as
identidades SAN fora do Git. A CA privada/leaf são criadas em
`%LOCALAPPDATA%\AndroidStreamDeck\tls` por padrão:

```bash
export STREAMDECK_HOST=0.0.0.0
export STREAMDECK_PORT=8765
export STREAMDECK_ADMIN_CODE='OUTRO_CODIGO_ADMINISTRATIVO_AQUI'
export STREAMDECK_REQUIRE_AUTH=true
export STREAMDECK_TLS_MODE=required
export STREAMDECK_TLS_IDENTITIES='192.168.1.44'
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync streamdeck-server
```

O código administrativo deve ter de 6 a 64 caracteres ASCII (`A-Z`, `a-z`, `0-9`,
`.`, `_` ou `-`). O servidor rejeita binds remotos sem autenticação ou TLS e o
certificado deve conter cada hostname/IP que será usado pelo Android. O
`STREAMDECK_PAIRING_CODE` continua aceito apenas para compatibilidade legada; o
fluxo recomendado não exige código estático.

Para o emulador Android padrão, o endpoint seguro é:

```text
https://10.0.2.2:8765
```

O certificado precisa conter `10.0.2.2` no SAN. Em um celular físico, use o IP
privado do Windows, com o mesmo IP incluído em `STREAMDECK_TLS_IDENTITIES`.
O firewall do Windows deve permitir a porta somente na rede privada apropriada;
essa regra ainda é uma etapa operacional manual.

## Pareamento e autenticação

O fluxo recomendado é temporário e não pede ao usuário client ID, porta, CA ou
trust code:

1. O tray/janela local cria uma sessão em `POST /api/v1/local/pairing-session`
   (somente loopback, com `X-StreamDeck-Admin-Code`). A resposta contém uma
   senha aleatória de 128 bits, `session_id`, validade, IP e o QR
   `streamdeck://pair/v1`; a sessão expira em 10 minutos e só pode ser usada uma
   vez.
2. No modo manual, o Android deriva o `session_id` da senha; no modo QR, valida
   estritamente o payload e confere que o ID deriva da senha recebida.
3. O Android faz `GET /api/v1/pairing/bootstrap?session_id=...` por um cliente
   TLS temporário. O bundle contém salt, CA, endereço, validade e prova HMAC.
4. A chave HKDF/HMAC derivada da senha autentica a prova do servidor. Somente
   depois disso a CA é instalada no `TrustManager` restrito e o Android envia
   `POST /api/v1/pairing/claim` com `session_id` e `client_proof`.
5. O servidor retorna o token opaco. O Android persiste token, endpoint, CA e
   identidade interna em armazenamento cifrado pelo Android Keystore; a senha
   temporária é descartada e nunca é usada na reconexão.

O `POST /api/v1/pairing/claim` legado com `pairing_code` permanece somente para
compatibilidade de migração. Não use esse caminho para novas instalações.

O WebSocket autenticado remoto é:

```text
wss://<host>:<porta>/api/v1/ws
```

O cliente envia o token dentro de `hello.payload.access_token`. Tokens ausentes
ou inválidos são rejeitados antes de carregar o perfil. O token não deve ser
colocado na URL, em logs ou em mensagens de diagnóstico.

A CA é bootstrapada dentro do bundle autenticado pela senha; o mDNS não concede
confiança. A comunicação HTTP/WS sem TLS fica restrita ao loopback de
desenvolvimento controlado. Não exponha o modo cleartext à rede.

A administração de dispositivos usa um código separado e explícito:

- `GET /api/v1/devices` — inventário sanitizado;
- `POST /api/v1/devices/<client_id>/revoke` com `{"reason": "lost_device"}` —
  revogação idempotente.

Envie o segredo somente no header `X-StreamDeck-Admin-Code`, sempre por
loopback ou HTTPS. Sem `STREAMDECK_ADMIN_CODE`, os endpoints ficam indisponíveis.
A resposta nunca contém token, hash de token, CA, IP ou modelo. Tentativas
inválidas de pareamento/administração são limitadas a cinco por origem por
janela de 60 segundos e retornam `429` quando excedidas. Revogação e reparing
fecham imediatamente as sessões WSS afetadas com `AUTH_REVOKED`/`1008`.

## Perfil inicial e migração

Em uma instalação nova, o servidor instala de forma transacional e idempotente o
perfil built-in `essential-controls` (`Controles essenciais`), com a página
`Principal` em uma grade 3 × 3 e oito controles. A nona célula permanece livre e
não interativa. O marcador `builtin_profile_installations` impede recriação
silenciosa após uma remoção voluntária.

Em um banco existente, a instalação nunca substitui o perfil ativo ou um perfil
personalizado. Se houver outro perfil ativo, o built-in é criado inativo; se o ID
já estiver ocupado por dados do usuário, a colisão é preservada e somente o
marcador de instalação é registrado. A migração para o schema 5 é idempotente e
executada dentro da transação do banco.

## API HTTP de perfil

A API fica sob `/api/v1`:

- `GET /api/v1/profile` retorna o perfil ativo.
- `GET /api/v1/profiles/{profile_id}/snapshot` retorna um snapshot; use
  `?revision=N` para revisão histórica (`N >= 1`).
- `GET /api/v1/actions` retorna o catálogo fechado: `hotkey`, `key`, `media`,
  `text`, `url`, `application`.
- `PUT /api/v1/profiles/{profile_id}?expected_revision=N` valida e persiste a
  próxima revisão.

Falhas usam sempre a forma sanitizada:

```json
{"code":"PROFILE_REVISION_CONFLICT","message":"Profile revision conflict","retryable":true}
```

O servidor não executa shell, `command`, `subprocess` ou ações arbitrárias. A
atualização de perfil usa revisão otimista; a auditoria está disponível em:

```text
GET /api/v1/profiles/{profile_id}/audit?limit=50
```

Essa rota devolve somente revisão, timestamp, origem e motivo; nunca devolve o
snapshot persistido.

## Execução de ações — perfil essencial

O registry permanece fechado. Os adaptadores validados cobrem `key`, `media`,
`text`, `url` e `application`; nenhum tipo aceita shell, caminho livre ou payload
executável enviado pelo Android.

O catálogo de aplicações é separado do catálogo de tipos: a única entrada de
produção é o ID `chrome`, exibido como `Google Chrome`. O cliente envia somente
`app_id=chrome`; o servidor resolve internamente o executável fixo `chrome.exe`,
sem aceitar caminho ou argumentos. A listagem sanitizada nunca devolve o nome do
executável. Se o Chrome não estiver disponível no Windows, o adaptador retorna
rejeição segura.

`PRINTSCREEN` faz parte da allowlist fechada de teclas e é convertido em
`VK_SNAPSHOT` (`0x2C`), com evento down/up. O comportamento do Windows coloca a
captura no clipboard; o servidor não salva, transmite nem registra a imagem.

Os oito controles do perfil inicial são:

| Controle | Ação fechada |
| --- | --- |
| Play/Pause | `media/play_pause` |
| Próxima | `media/next` |
| Mute | `media/mute` |
| Spotify | `media/play_pause` na sessão global ativa |
| Chrome | `application/chrome` |
| Volume + | `media/volume_up` |
| Volume − | `media/volume_down` |
| Print Screen | `key/PRINTSCREEN` |

O tile Spotify usa a sessão multimídia global do Windows; ele não implementa
Spotify OAuth nem garante exclusividade sobre outros players.

O cliente Android valida o snapshot e envia somente IDs/revisão no `press`.
A página inicial é 3 × 3, e a nona célula é vazia e não clicável.

O modo `STREAMDECK_ACTION_MODE=recording` existe apenas para o harness isolado
de UI/protocolo: valida as mesmas ações, registra o tipo em memória e não abre
aplicativos, emite teclas ou toca no clipboard. Não habilite esse modo em uma
instalação de produção.

## WebSocket e limites

Handshake normal:

1. cliente envia `hello` com identidade, versão, `[1]` e token;
2. servidor responde `welcome` e `profile_snapshot`;
3. `ping` recebe `pong` com o mesmo `nonce`;
4. `press` para uma `hotkey` permitida retorna `ack/completed`; tipos sem
   adaptador retornam `ack/rejected`, preservando a idempotência do `request_id`;
5. alterações HTTP geram `profile_changed` para sessões do mesmo perfil.

Limites de transporte:

- no máximo `32` conexões simultâneas;
- frame textual máximo de `256 KiB`;
- timeout de handshake de `5 s`;
- timeout de inatividade de `60 s`;
- envio de broadcast com timeout individual de `1 s`;
- conexões lentas/quebradas são removidas sem bloquear as demais.

## Verificações de desenvolvimento

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync pytest -q
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync ruff check .
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync ruff format --check .
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync python -m compileall -q app scripts
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync bandit -q -ll -r app scripts
uv lock --check
git diff --check
```
