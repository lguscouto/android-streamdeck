# Contrato compartilhado do Android Stream Deck

## Versão e arquivos

Esta pasta define a versão **1** (`protocol_version: 1`) do contrato entre o aplicativo Android e o servidor Windows. Os schemas usam **JSON Schema Draft 2020-12** e rejeitam propriedades desconhecidas nos objetos do protocolo.

- `v1-profile.schema.json`: perfil, páginas, posições e ações permitidas.
- `v1-message.schema.json`: envelope e mensagens WebSocket.
- `../fixtures/default-profile.json`: perfil mínimo válido e seguro para desenvolvimento.
- `../fixtures/essential-controls-profile.json`: perfil built-in 3 × 4 com onze controles, incluindo telemetria de CPU, memória e GPU/VRAM.
- `../fixtures/invalid-messages.json`: catálogo de envelopes intencionalmente inválidos para testes de rejeição.

Os nomes dos campos permanecem em inglês para manter um protocolo estável; esta documentação está em PT-BR.

## Perfil

Um perfil contém `id`, `name`, `revision`, `active_page_id` e `pages`. Cada página declara explicitamente `id`, `title`, `order`, `rows`, `columns` e `buttons`. Cada botão declara `id`, `row`, `column`, `title` e `action`, podendo também informar `icon` e `color`.

- IDs devem ser estáveis, sem espaços ou caminhos, e não devem ser derivados da posição no array.
- `row` e `column` são posições explícitas e começam em zero. A ordem dos objetos no JSON não tem significado visual.
- `order` também é explícito; consumidores não devem depender da ordem em que as páginas aparecem no array.
- `revision` começa em 1 e identifica a versão do conteúdo do perfil.
- O JSON Schema garante a forma e os limites individuais. A validação Pydantic do servidor deve garantir que os IDs de perfis, páginas e botões sejam únicos, que `active_page_id` exista, que cada botão esteja dentro de `rows`/`columns` e que não haja dois botões na mesma posição `(row, column)` da mesma página. Essa última regra é relacional e não é expressa neste JSON Schema.

## Ações permitidas

`action.type` é um enum fechado:

| Tipo | Campos obrigatórios | Regra |
| --- | --- | --- |
| `hotkey` | `modifiers`, `key` | Modificadores pertencem a uma lista fechada (`ctrl`, `alt`, `shift`, `win`). |
| `key` | `key` | Uma tecla única, sem comando de sistema livre; `PRINTSCREEN` é a entrada fechada para `VK_SNAPSHOT`. |
| `media` | `command` | `command` é uma enumeração fechada de controles multimídia (`play_pause`, `next`, `previous`, `stop`, `volume_up`, `volume_down`, `mute`). |
| `text` | `text` | Texto limitado pelo schema; não é um comando para o shell. |
| `url` | `url` | Apenas URLs `https://` são aceitas pelo contrato. |
| `application` | `app_id` | `app_id` é um identificador lógico de aplicativo previamente registrado no servidor, nunca um caminho enviado pelo cliente. |
| `system_info` | `target` | Telemetria interna com `target` fechado em `cpu`, `memory` ou `gpu`; não aceita consulta WMI, comando ou diagnóstico arbitrário. |

A propriedade `command` só existe no caso `media` e só aceita os valores do enum acima. Não existe uma ação genérica de shell ou de diagnóstico.

## Envelope de mensagens

Toda mensagem tem a forma:

```json
{
  "protocol_version": 1,
  "type": "press",
  "payload": {
    "request_id": "req-001",
    "profile_id": "default",
    "page_id": "main",
    "button_id": "media-play-pause",
    "revision": 1
  }
}
```

Os tipos suportados na versão 1 são `hello`, `welcome`, `press`, `ack`, `error`, `ping`, `pong`, `profile_snapshot` e `profile_changed`.

- `hello` anuncia `client_id`, `client_version` e `supported_protocol_versions`.
- `welcome` confirma o servidor e o perfil/revisão selecionados.
- `press` referencia somente `request_id`, `profile_id`, `page_id`, `button_id` e `revision`. Não leva `shell`, `command`, caminho ou payload de execução.
- `ack` confirma uma solicitação com status `accepted`, `completed` ou `rejected`.
- `error` retorna um código e mensagem estruturados, podendo referenciar `request_id`.
- `ping` e `pong` carregam um `nonce` para verificação de conectividade.
- `profile_snapshot` carrega um perfil completo conforme `v1-profile.schema.json`.
- `profile_changed` informa `profile_id` e `revision`; o cliente pode solicitar um novo snapshot.

Os payloads também são objetos fechados. Campos novos ou desconhecidos devem ser rejeitados até que uma versão compatível do contrato seja publicada.

## Compatibilidade

Um consumidor deve verificar `protocol_version` antes de processar a mensagem e anunciar as versões que suporta no `hello`. A versão 1 é compatível apenas com os tipos, enums e campos definidos neste diretório. Mudanças que alterem a semântica, removam campos, ampliem uma enumeração de forma incompatível ou mudem requisitos devem gerar uma nova versão (`v2-*` e `protocol_version: 2`). A `revision` de um perfil não substitui a versão do protocolo: ela serve apenas para detectar conteúdo desatualizado.

O `profile_snapshot` referencia o schema de perfil no mesmo diretório; validadores devem resolver `v1-profile.schema.json` ao validar essa mensagem.

## Limite de segurança

O servidor **nunca executa comandos arbitrários** recebidos do cliente. O cliente seleciona um botão por IDs estáveis; o servidor resolve o botão no perfil vigente, confere a revisão e encaminha somente para um adaptador interno de uma allowlist. Não deve interpretar, concatenar ou repassar `shell`, `cmd`, `command` livre, caminho de executável ou script.

Tentativas de adicionar propriedades desconhecidas, `shell`, um `command` fora de `media` ou um `media.command` que não esteja no enum devem ser rejeitadas antes de qualquer execução. O fixture `invalid-messages.json` contém exemplos neutros dessas tentativas; ele não deve ser enviado a um servidor de produção.

O perfil built-in `essential-controls` usa a página `Principal` em uma grade 3 × 4
com onze controles: Play/Pause, Próxima, Mute, Spotify, Chrome, Volume +,
GPU & VRAM, Volume −, Print Screen, CPU & Temp e Memória. Os três controles de
telemetria usam, respectivamente, `system_info/gpu`, `system_info/cpu` e
`system_info/memory`; o cliente continua
referenciando apenas o botão, nunca uma consulta WMI ou comando. `application/chrome`
resolve somente o ID catalogado `chrome` no servidor; o cliente nunca envia caminho
ou argumentos. Spotify usa a sessão multimídia global e Print Screen não transporta
a imagem pelo protocolo.

O perfil de exemplo contém apenas uma configuração de hotkey `Ctrl+Shift+S`, um controle multimídia e uma URL HTTPS de documentação. Esses botões são dados de configuração: esta tarefa não executa nenhuma ação.

## Validação local

A sintaxe pode ser verificada sem dependências adicionais:

```bash
python3 -m json.tool shared/protocol/v1-profile.schema.json >/dev/null
python3 -m json.tool shared/protocol/v1-message.schema.json >/dev/null
python3 -m json.tool shared/fixtures/default-profile.json >/dev/null
python3 -m json.tool shared/fixtures/essential-controls-profile.json >/dev/null
python3 -m json.tool shared/fixtures/invalid-messages.json >/dev/null
```

A validação relacional do perfil deve ficar no modelo Pydantic do servidor, além da validação JSON Schema. O servidor declara `jsonschema` como dependência de runtime (`server/pyproject.toml`) e usa um validador Draft 2020-12 em `server/app/profile_transfer.py`, registrando localmente os `$ref` para não tocar a rede.
