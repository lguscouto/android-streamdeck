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
- pareamento: desabilitado no modo loopback sem código configurado

O endpoint de saúde padrão é `http://127.0.0.1:8765/health`.

O arquivo `.env.example` é apenas documentação e não é carregado automaticamente.
Não grave códigos de pareamento, tokens ou outras credenciais no repositório.

## Operação no Windows — Fase 6

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
STREAMDECK_PAIRING_CODE=<código fora do Git>
STREAMDECK_DISCOVERY_ENABLED=true
STREAMDECK_DISCOVERY_NAME=Android Stream Deck
```

O tipo anunciado é `_android-streamdeck._tcp.local.`. O anúncio contém apenas
versão do protocolo, porta e `requires_pairing=true`; não contém código de
pareamento, token, caminho, banco ou snapshot. O primeiro pareamento continua
funcionando por endereço digitado manualmente, sem depender do mDNS. A
configuração de descoberta é rejeitada em loopback, wildcard, hostname, IP público
ou rede reservada; use somente um IPv4 RFC1918 concreto (`10/8`, `172.16/12` ou
`192.168/16`).

### Bundle Windows e smoke

A partir de `server/`, com as dependências de desenvolvimento instaladas:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --group dev python scripts/build_windows.py
env -u PYTHONPATH -u VIRTUAL_ENV uv run --group dev python scripts/smoke_windows_bundle.py
```

O build gera, fora do Git, `dist/streamdeck-server.exe` e
`dist/streamdeck-tray.exe`. O smoke usa banco temporário, porta loopback efêmera,
consulta `/health`, encerra o processo e verifica que a porta foi liberada.

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

O bind remoto exige autenticação. Configure um código de pareamento fora do Git e
inicie o servidor, por exemplo:

```bash
export STREAMDECK_HOST=0.0.0.0
export STREAMDECK_PORT=8765
export STREAMDECK_PAIRING_CODE='COLOQUE_SEU_CODIGO_AQUI'
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync streamdeck-server
```

O código deve ter de 6 a 64 caracteres ASCII (`A-Z`, `a-z`, `0-9`, `.`, `_` ou
`-`). Quando `STREAMDECK_PAIRING_CODE` existe, `STREAMDECK_REQUIRE_AUTH` assume
`true` automaticamente. O servidor rejeita binds remotos sem autenticação.

Para o emulador Android padrão, use no aplicativo:

```text
http://10.0.2.2:8765
```

Em um celular físico, use o IP privado do Windows na rede local, por exemplo
`http://192.168.x.x:8765`. O firewall do Windows deve permitir a porta somente
na rede privada apropriada; essa regra ainda é uma etapa operacional manual.

## Pareamento e autenticação

O endpoint de pareamento é:

```text
POST /api/v1/pairing/claim
```

Corpo:

```json
{
  "client_id": "android-emulator",
  "client_version": "0.1.0",
  "pairing_code": "<código configurado fora do repositório>"
}
```

A resposta contém um token opaco. O banco grava somente o hash SHA-256 do token;
o token em claro é retornado apenas nessa resposta. O aplicativo Android o
armazena criptografado com AES-GCM, por uma chave não exportável do Android
Keystore, e o vincula ao endpoint que emitiu o pareamento. Um novo pareamento do
mesmo `client_id` substitui o token anterior.

O WebSocket autenticado é:

```text
ws://<host>:<porta>/api/v1/ws
```

O cliente envia o token dentro de `hello.payload.access_token`. Tokens ausentes
ou inválidos são rejeitados antes de carregar o perfil. O token não deve ser
colocado na URL, em logs ou em mensagens de diagnóstico.

A comunicação desta fase usa HTTP/WS na rede local. Não exponha a porta à
internet. TLS/mTLS e rotação administrativa de dispositivos pertencem ao
hardening posterior.

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

## Execução de ações — Fase 4

O registry permanece fechado. Além de `hotkey`, há adaptadores específicos para
`key`, `media`, `text` e `url`. `application` continua explicitamente rejeitada
até existir um catálogo seguro de aplicativos permitidos. Nenhum tipo aceita
shell, caminho livre ou payload executável enviado pelo Android.

O cliente Android valida o snapshot e envia somente IDs/revisão no `press`. O
perfil de desenvolvimento fornece uma grade de 3 colunas × 5 linhas para a
página principal.

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
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync python -m compileall -q app
uv lock --check
git diff --check
```
