# Fase 7 — Transporte LAN seguro e gestão de dispositivos

## Escopo entregue

A Fase 7 adiciona transporte seguro para acesso remoto do Android ao servidor
Windows, bootstrap explícito de confiança e ciclo de vida de credenciais pareadas.
O bind padrão do servidor continua em `127.0.0.1` e pode permanecer sem TLS para
uso local controlado; qualquer bind remoto exige autenticação e TLS.

### Servidor

- CA privada persistente e leaf renovável, fora do checkout e do bundle;
- SANs explícitos para as identidades usadas pelo cliente;
- validação de cadeia, chave, validade, `BasicConstraints`, `KeyUsage`, EKU,
  SKI/AKI e identidades ao carregar o material;
- lock interprocessos e escrita atômica;
- DACL NTFS restritiva para o SID do usuário operacional no Windows;
- `HTTPS`/`WSS` obrigatório para bind remoto;
- inventário mínimo de clientes pareados, geração de credencial, revogação,
  rotação por novo pareamento e auditoria sem segredos;
- sessões WebSocket abertas são invalidadas imediatamente após revogação ou
  reparing, com erro `AUTH_REVOKED` e fechamento `1008`;
- tentativas inválidas de pareamento e administração são limitadas a cinco por
  origem a cada 60 segundos, com resposta sanitizada `429`;
- mDNS/DNS-SD opt-in e sem segredos. O anúncio informa somente protocolo,
  pareamento requerido, `transport=https` e `tls=required`.

### Android

- `ServerEndpoint` aceita apenas `https://` e deriva somente `wss://`;
- o formulário expõe apenas IP e senha temporária; client ID e porta são
  internos;
- bootstrap TLS temporário autentica a CA por prova HMAC/HKDF derivada da senha;
  o `TrustManager` só é criado depois dessa prova;
- QR offline `streamdeck://pair/v1` é mínimo, versionado, estrito e vinculado à
  sessão de uso único;
- OkHttp REST e WebSocket usam o mesmo trust manager limitado à CA validada e
  mantêm a verificação padrão de hostname/SAN;
- sem bundle/prova verificados, nenhum cliente de rede autenticado é criado e a
  operação falha localmente;
- endpoint, client ID, token, CA PEM e código são persistidos juntos com
  AES-GCM por chave não exportável do Android Keystore;
- PEM recebido em uma única linha é normalizado para o formato canônico antes
  do parse, sem reduzir a validação criptográfica.

## Configuração remota no Windows

O diretório padrão para estado mutável TLS é:

```text
%LOCALAPPDATA%\AndroidStreamDeck\tls
```

Exemplo conceitual — substitua a identidade e o código por valores locais, sem
registrá-los no Git:

```text
STREAMDECK_HOST=192.168.1.44
STREAMDECK_PORT=8765
STREAMDECK_ADMIN_CODE=<código administrativo separado, fora do Git>
STREAMDECK_REQUIRE_AUTH=true
STREAMDECK_TLS_MODE=required
STREAMDECK_TLS_IDENTITIES=192.168.1.44
STREAMDECK_DISCOVERY_ENABLED=false
```

Com um IPv4 RFC1918 concreto em `STREAMDECK_HOST`, o runner abre dois sockets
explícitos na mesma porta: o IPv4 configurado para HTTPS/WSS do Android e
`127.0.0.1` para a administração local do tray. O endereço divulgado e o SAN do
Android continuam sendo o IPv4 privado; a rota `LOCAL_ONLY` permanece
inacessível pela rede. Nenhuma outra interface é adicionada implicitamente.

O servidor gera ou valida a CA e o leaf nesse diretório. A janela local gera uma
senha temporária aleatória e o QR correspondente; não copie `ca-key.pem`,
`leaf-key.pem`, tokens ou o banco para o telefone. A CA pública do bundle só é
aceita depois da prova derivada da senha.

A administração de dispositivos é deliberadamente separada do pareamento:
`STREAMDECK_ADMIN_CODE` habilita `GET /api/v1/devices` e
`POST /api/v1/devices/{client_id}/revoke`. Sem esse segredo explícito, os
endpoints retornam indisponibilidade. A resposta do inventário contém somente
client ID, versão, plataforma, geração, horários e estado de revogação; não
expõe hash de token nem material de confiança.

Para o emulador Android padrão, o E2E usa `10.0.2.2` como identidade adicional:

```text
https://10.0.2.2:8765
```

Em um telefone físico, use o IP privado real do Windows e inclua esse IP em
`STREAMDECK_TLS_IDENTITIES`. O certificado precisa conter SAN correspondente à
identidade que será digitada no Android.

## mDNS

A descoberta permanece opcional e não é uma raiz de confiança. Ela não fornece
CA, fingerprint, código, token ou autorização. O cliente pode continuar usando
endpoint manual; o pareamento e o trust bootstrap sempre exigem confirmação
explícita.

## Validação

No diretório `server/`:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync pytest -q
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync ruff check .
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync python -m compileall -q app scripts
uv lock --check
git diff --check
```

Smoke HTTPS do servidor, com estado e banco temporários:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync \
  python scripts/phase7_tls_smoke.py
```

E2E real Android ↔ Uvicorn HTTPS/WSS, usando o emulador conectado e estado
sintético temporário:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync \
  python scripts/phase7_android_e2e.py
```

O script E2E executa exatamente `OnboardingFlowInstrumentedTest`,
`VisualGoldenInstrumentedTest` e `PairingFlowInstrumentedTest`, verificando
onboarding, pareamento, execução de ações, edição de perfil e reconexão com
credencial cifrada. O harness remove screenshots temporários (`pairing`,
`editor`, `deck-main`, `deck-secondary` e `settings`), fixture Android, processo,
porta, banco e material TLS; qualquer falha de cleanup impede o marcador de
sucesso.

No diretório `android/`, com o JBR/SDK configurados:

```bash
./gradlew :app:testDebugUnitTest
./gradlew :app:assembleDebug
./gradlew :app:assembleDebugAndroidTest
./gradlew :app:connectedDebugAndroidTest
```

O teste instrumentado de fluxo completo exige argumentos explícitos de IP privado
e senha temporária. A sessão é criada localmente pelo harness e o teste nunca
cai para HTTP.

## Limitações conhecidas

- A validação funcional foi feita no emulador `Pixel_8` API 37 (`1080x2400`,
  densidade 420); o Galaxy A10 físico ainda não foi conectado e não está
  certificado.
- O artefato Android validado nesta fase é o APK debug e seu APK de testes. A
  assinatura de release e a distribuição final continuam sendo uma etapa de
  publicação separada.
- O uso de mDNS pelo cliente Android não é necessário para a segurança nem para
  o pareamento manual; a implementação não deve transformar anúncios em
  confiança automática.

## Limpeza obrigatória

Após os gates, confirme que não há servidor/smoke em execução, que a porta de
teste foi liberada, que nenhum banco/certificado temporário está no checkout e
que o monitor temporário `streamdeck-fase7-progresso` foi removido somente após
a publicação verificável da fase.
