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

As **Fases 1, 2 e 3** estão implementadas e validadas no `Pixel_8`.
A Fase 3 entrega a primeira ação autenticada ponta a ponta.

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

### Fase 3 — execução controlada

- registry interno fechado para ações;
- primeira hotkey Windows via `keybd_event` e mapa explícito de teclas virtuais;
- Android valida o `profile_snapshot` e mostra a página ativa em grade configurada
  por `rows × columns` (perfil de desenvolvimento: 3 colunas × 5 linhas);
- toque envia somente `request_id`, IDs e revisão; nenhuma hotkey ou comando sai
  do Android;
- `ack/completed`, `ack/rejected` e `error` atualizam o botão correto como
  `Concluído` ou `Erro`, com bloqueio durante execução;
- smoke UiAutomator no `Pixel_8` comprovou pareamento, WebSocket, grade, hotkey
  registrada, rejeição segura e reconexão criptografada;
- `media`, `text`, `url`, `key` e `application` continuam rejeitadas até que
  recebam adaptadores específicos, testados e seguros.

### Acesso local padrão

- Health: `http://127.0.0.1:8765/health`
- API: `http://127.0.0.1:8765/api/v1`
- WebSocket: `ws://127.0.0.1:8765/api/v1/ws`

O bind padrão é loopback. O pareamento e a autenticação do WebSocket estão
implementados, inclusive no cliente Android. O token Android é criptografado com
AES-GCM por chave não exportável no Android Keystore e permanece vinculado ao
endpoint que o emitiu. A primeira hotkey só é emitida pelo adaptador Windows a
partir de teclas virtuais permitidas; não há shell, comando livre ou caminho
recebido do cliente. A grade Android e os estados de execução foram validados no
`Pixel_8`; consulte [`docs/phase-3-delivery.md`](docs/phase-3-delivery.md) para
o smoke controlado, comandos e limitações.

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

- Fase 4: editor de perfis/layouts, novos adaptadores fechados e recarga do
  snapshot após alterações remotas;
- fases posteriores: descoberta, TLS/mTLS, empacotamento e release verificável.
