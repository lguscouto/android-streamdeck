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
- banco: `server/data/streamdeck.sqlite3`
- pareamento: desabilitado no modo loopback sem código configurado

O endpoint de saúde padrão é `http://127.0.0.1:8765/health`.

O arquivo `.env.example` é apenas documentação e não é carregado automaticamente.
Não grave códigos de pareamento, tokens ou outras credenciais no repositório.

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

O servidor não executa shell, `command`, `subprocess` ou ações arbitrárias.

## Execução de ações — primeira fatia da Fase 3

O registry do servidor está fechado. Nesta etapa, somente a ação `hotkey` possui
adaptador ativo: modificadores e tecla são transformados por um mapa interno de
virtual keys e emitidos no Windows por `keybd_event`. Nenhum comando de shell,
caminho ou argumento livre é montado a partir do cliente.

As ações `key`, `media`, `text`, `url` e `application` continuam sem adaptador e
recebem `ack` com `status: "rejected"`. Elas só serão habilitadas com contratos e
testes específicos nas próximas fatias.

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
