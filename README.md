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

Esta tarefa cria apenas o esqueleto e a documentação; a implementação Android e do servidor será feita nas próximas tarefas.

## Estrutura

```text
android-streamdeck/
├── android/    # Aplicativo Android Kotlin/Compose
├── server/     # Servidor Python/FastAPI/WebSocket
├── shared/     # Contratos e documentação compartilhados
├── docs/       # Arquitetura e decisões do projeto
└── scripts/    # Scripts auxiliares de desenvolvimento
```

## Próximos comandos

Os comandos abaixo são os próximos passos previstos após o scaffold:

```bash
cd E:/projetos/android-streamdeck

# Verificar a árvore e o estado do repositório
git status --short --branch

# Próximas tarefas: criar o projeto Android e o ambiente do servidor
# (os comandos concretos serão adicionados quando essas tarefas forem executadas)
```

Consulte [`docs/architecture.md`](docs/architecture.md) antes de implementar novos fluxos de rede ou ações.
