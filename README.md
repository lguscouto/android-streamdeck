# Android Stream Deck + Windows Server

## Objetivo

Construir um painel de controle Android para acionar, pela rede local, um conjunto pequeno e explícito de ações registradas em um servidor Windows. O produto deve oferecer botões configuráveis, feedback de execução e uma fronteira de segurança clara: o servidor nunca aceitará comandos shell arbitrários enviados pelo cliente.

## Escopo do MVP

- Aplicativo Android nativo em Kotlin com Jetpack Compose.
- Cliente de rede baseado em OkHttp para comunicação com o servidor.
- Servidor Python com FastAPI e WebSocket.
- Persistência local em SQLite para ações, configurações mínimas e histórico necessário ao MVP.
- Descoberta/configuração manual do endereço do servidor na rede local.
- Catálogo de ações previamente registradas no servidor, com execução somente por identificador e payload validado.
- Estados básicos de conexão, execução, sucesso e erro visíveis no aplicativo.
- Sem acesso pela internet, sem sincronização em nuvem e sem execução de shell command arbitrário.

## Estado atual

As **Fases 1 e 2** estão implementadas localmente.

### Fase 1 — servidor e contratos

- SQLite versionado com migração, FKs e histórico de revisões;
- seed idempotente do perfil padrão e recuperação segura após reinício;
- API HTTP versionada em `/api/v1` para perfil, snapshots, catálogo de ações e
  atualização otimista por revisão;
- WebSocket em `/api/v1/ws` com `hello`, `welcome`, snapshot, ping/pong,
  validação de `press`, `ack`/`error`, timeout e `profile_changed`;
- envelopes fechados, sem shell/command arbitrário;
- respostas de erro sanitizadas, sem SQL, caminhos, segredos ou tracebacks.

### Fase 2 — pareamento e transporte autenticado

- endpoint HTTP de pareamento com código manual mantido fora do Git;
- token opaco aleatório, persistido no SQLite do servidor apenas como hash;
- autenticação obrigatória do WebSocket para bind remoto;
- cliente Android com OkHttp para pareamento, WebSocket autenticado e
  sincronização de snapshot do perfil;
- token Android criptografado com AES-GCM, com chave não exportável no Android
  Keystore, e vinculado ao endpoint que o emitiu;
- cleartext HTTP/WS permitido apenas no manifesto `debug`; o manifesto principal
  mantém `usesCleartextTraffic=false`.

Acesso local padrão:

- Health: `http://127.0.0.1:8765/health`
- API: `http://127.0.0.1:8765/api/v1`
- WebSocket: `ws://127.0.0.1:8765/api/v1/ws`

O bind padrão é loopback. O pareamento e a autenticação do WebSocket estão
implementados, inclusive no cliente Android. O token Android é criptografado com
AES-GCM por chave não exportável no Android Keystore e permanece vinculado ao
endpoint que o emitiu. Adaptadores de execução de ações e a exposição operacional
segura na LAN permanecem para as fases seguintes. Nesta fase, um `press` válido é
reconhecido, mas retorna `rejected` porque a execução ainda não foi habilitada.

Validação atual do servidor:

```bash
cd E:/projetos/android-streamdeck/server
env -u PYTHONPATH -u VIRTUAL_ENV uv run pytest -q
env -u PYTHONPATH -u VIRTUAL_ENV uv run ruff check .
env -u PYTHONPATH -u VIRTUAL_ENV uv run python -m compileall -q app
uv lock --check
```

## Estrutura

```text
android-streamdeck/
├── android/    # Aplicativo Android Kotlin/Compose
├── server/     # Servidor Python/FastAPI/WebSocket
├── shared/     # Contratos e documentação compartilhados
├── docs/       # Arquitetura e decisões do projeto
└── scripts/    # Scripts auxiliares de desenvolvimento
```

## Executar o servidor local

```bash
cd E:/projetos/android-streamdeck/server
uv run streamdeck-server
```

Com os valores padrão, consulte `http://127.0.0.1:8765/health`. Para
configurar uma base SQLite diferente, defina `STREAMDECK_DATABASE_PATH`; o
padrão é `server/data/streamdeck.sqlite3`, ignorado pelo Git. Consulte
[`server/README.md`](server/README.md) para o contrato HTTP e WebSocket.

## Próximas fases

- Fase 3: grade funcional e primeira ação end-to-end;
- fases seguintes: editor, perfis, descoberta, TLS/mTLS, empacotamento e release
  verificável.
