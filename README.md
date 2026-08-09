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

A **Fase 1 do servidor** está implementada localmente:

- SQLite versionado com migração, FKs e histórico de revisões;
- seed idempotente do perfil padrão e recuperação segura após reinício;
- API HTTP versionada em `/api/v1` para perfil, snapshots, catálogo de ações e
  atualização otimista por revisão;
- WebSocket em `/api/v1/ws` com `hello`, `welcome`, snapshot, ping/pong,
  validação de `press`, `ack`/`error`, timeout e `profile_changed`;
- envelopes fechados, sem shell/command arbitrário;
- respostas de erro sanitizadas, sem SQL, caminhos, segredos ou tracebacks.

Acesso local padrão:

- Health: `http://127.0.0.1:8765/health`
- API: `http://127.0.0.1:8765/api/v1`
- WebSocket: `ws://127.0.0.1:8765/api/v1/ws`

O bind padrão é loopback. Pareamento, autenticação, cliente Android conectado,
adaptadores de execução de ações e exposição segura na LAN permanecem nas fases
seguintes. Nesta fase, um `press` válido é reconhecido, mas retorna `rejected`
porque a execução ainda não foi habilitada.

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

- Fase 2: pareamento, autenticação do WebSocket e cliente Android de rede;
- Fase 3: grade funcional e primeira ação end-to-end;
- fases seguintes: editor, perfis, descoberta, empacotamento, hardening e
  release verificável.
