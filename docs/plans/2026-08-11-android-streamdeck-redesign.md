# Android StreamDeck — Plano de Redesign Completo

> **Para o Hermes:** implementar este plano por slices verticais, carregando `software-development/android-native-development` e `software-development/subagent-driven-development`. A suspensão anterior de testes deixou de ser aplicada quando Gustavo pediu a execução do plano; ainda assim, E2E/publicação exigem gates separados e não são concluídos implicitamente.

**Objetivo:** substituir a interface provisória por uma experiência Android coesa, rápida e visualmente reconhecível, centrada no deck, sem alterar os contratos HTTPS/WSS, as garantias de segurança nem as regras de concorrência já implementadas.

**Arquitetura:** manter Jetpack Compose e os modelos de rede atuais, mas separar o monólito visual de `App.kt` em shell, estado de navegação, telas e componentes reutilizáveis. Um sistema de design próprio fornecerá cores, tipografia, formas, espaçamento, ícones e estados; a grade continuará obedecendo às linhas/colunas recebidas do servidor.

**Stack:** Kotlin, Jetpack Compose, Material 3, Material Symbols/ícones vetoriais, recursos Android, APIs nativas de haptics/animação, testes Compose/UiAutomator quando novamente autorizados.

**Data da análise:** 2026-08-11
**Referências estudadas:** WebDeck `e6820b1`, Macro Deck `9eebc0d`, Macro Deck Client `f48be9a`.

---

## 1. Diagnóstico do aplicativo atual

### 1.1 Problemas estruturais

1. `StreamDeckApp()` usa `MaterialTheme` sem um tema de produto; a aparência depende quase integralmente dos defaults do Material 3.
2. `themes.xml` força um tema Android claro, barras brancas e apenas um `colorAccent`, sem paletas claro/escuro ou tratamento edge-to-edge coerente.
3. `App.kt` concentra conexão, navegação, editor, gestão e renderização em mais de mil linhas; isso dificulta consistência visual, previews e evolução isolada das telas.
4. A navegação é composta por condicionais booleanas (`editingProfile`, `managingProfiles`) em vez de destinos explícitos. O usuário não recebe uma arquitetura espacial clara.
5. A tela principal mistura marca, página, status técnico, grade e três botões administrativos de largura total. O deck — tarefa principal — perde área útil.

### 1.2 Problemas visuais

1. Não existe identidade visual: fundo, superfícies, tipografia, raios, bordas e elevação não formam uma linguagem reconhecível.
2. Os botões da grade são `Button` Material padrão e parecem botões de formulário, não teclas físicas/virtuais de um macro pad.
3. A iconografia usa caracteres Unicode (`⌨`, `▶`, `▤`, `●`), inconsistentes entre fontes, versões do Android e fabricantes.
4. Células vazias são retângulos cinza visíveis, gerando ruído e aparência de protótipo.
5. O título ocupa até três linhas e compete com ícone e estado dentro de uma célula quadrada pequena.
6. A cor HEX do servidor é aplicada diretamente como superfície, sem garantia de contraste do conteúdo.
7. Feedback de execução troca a composição do botão por spinner/texto, causando instabilidade visual e excesso de informação.
8. Não há diferenciação clara entre estado normal, pressionado, executando, concluído, rejeitado, desabilitado e offline.

### 1.3 Problemas dos fluxos secundários

#### Pareamento

- Cinco campos técnicos aparecem de uma vez, incluindo CA PEM extensa e código de confiança.
- Não há progressão, resumo visual de segurança, separação entre dados básicos e configuração avançada nem estado de sucesso dedicado.
- A marca e o valor do produto não aparecem antes da configuração.

#### Editor

- Formulário linear muito longo, sem preview do botão.
- Seleção de botão por faixa horizontal de textos.
- Tipo de ação e comando de mídia mudam por ciclos sucessivos em um botão, sem lista ou contexto.
- Usuário precisa digitar identificador de ícone e cor HEX manualmente.
- Linha e coluna aparecem como campos técnicos, não como manipulação espacial.
- Ações principais ficam no fim da rolagem e podem ser encobertas pelo teclado.

#### Gerenciamento de perfis e páginas

- Perfis, criação, renomeação, duplicação, exclusão, páginas e JSON aparecem simultaneamente na mesma tela.
- IDs internos e revisões dominam os rótulos.
- Ações perigosas não possuem hierarquia nem confirmação visual adequada.
- `RETRY`, `RELOAD` e `CANCEL` aparecem em inglês e como detalhes técnicos do protocolo.
- Importação/exportação expõe JSON bruto em caixas de texto, em vez de usar arquivos e ações do sistema.

### 1.4 Problemas de conteúdo e acessibilidade

- Muitas strings visíveis estão hardcoded em Kotlin, fora de `strings.xml`.
- A semântica adicionada na Fase 10 é um bom começo, mas faltam agrupamento, foco, contraste previsível e alvos mínimos consistentes.
- Não há preferência de reduzir animações, contraste reforçado ou suporte explícito a escalas maiores de fonte.
- Estados de erro e sucesso aparecem como textos soltos em vez de componentes semânticos consistentes.

---

## 2. Análise das referências

## 2.1 WebDeck

### O que funciona

- Prioriza o canvas: quase toda a tela vira superfície de controle.
- Permite fundos, temas, cores por botão e imagens próprias.
- Botões usam ícones grandes e rótulos curtos.
- Pastas funcionam como páginas e reduzem a necessidade de navegação administrativa durante o uso.
- Aceita widgets informativos, como CPU, GPU, RAM e disco.
- Edição é contextual: cada posição vazia pode virar botão e cada botão pode ser editado no próprio canvas.
- O layout serve bem telas em paisagem e dispositivos reaproveitados como painéis dedicados.

### O que não deve ser copiado

- Os estilos são inconsistentes: cartões brancos, cartões escuros, ícones de origens diferentes e sombras variadas coexistem sem regra clara.
- O fundo decorativo compete com os controles e reduz contraste dos rótulos.
- Há muito espaço vazio sem estrutura responsiva clara.
- Rótulos pequenos fora dos cartões dificultam leitura e associação.
- CSS usa dimensões fixas e comportamento de desktop, inadequado como base nativa Android.
- Parte da personalização vira ruído visual. O redesign deve oferecer liberdade dentro de limites de legibilidade.

### Aprendizado para o nosso app

Adotar personalização controlada: cor, ícone e imagem por botão, plano de fundo opcional com overlay automático, páginas acessíveis e deck ocupando o máximo da tela. Não copiar CSS, assets ou código GPL.

## 2.2 Macro Deck desktop

### O que funciona

- Shell escuro estável com navegação lateral por ícones.
- Área de deck claramente separada de perfis, pastas e configurações.
- Perfis, árvore de pastas, grade e parâmetros do grid coexistem em uma hierarquia legível.
- Botões são tratados como objetos visuais: fundo, foreground, label, borda, raio, GIF e indicadores.
- A grade do desktop corresponde ao cliente móvel, criando previsibilidade.
- Menus contextuais permitem editar, copiar, colar, excluir e simular interações sem poluir o estado normal.
- Ecossistema de plugins e icon packs inspira uma arquitetura futura de catálogo, sem ser requisito desta fase.

### O que não deve ser copiado

- A interface WinForms/Tahoma é densa e visualmente datada.
- Muitos controles técnicos permanecem visíveis ao mesmo tempo.
- Bordas pesadas e faixas diagonais de estado geram ruído.
- A navegação lateral desktop não deve ser transplantada literalmente para telefone compacto.

## 2.3 Macro Deck Client

### O que funciona

- Deck em tela cheia e menu administrativo recolhido.
- Grade ocupa 100% da área e respeita orientação.
- Botões usam camadas independentes de background, ícone e foreground.
- Pressionar reduz o botão para `scale(0.9)` e a soltura tem animação própria, fornecendo feedback tátil visual imediato.
- Conexões salvas têm estado disponível/indisponível, SSL, autoconexão, reordenação e ações contextuais.
- Pareamento rápido por QR é separado do modo manual.
- Estados de conectando, falha, conexão perdida e conexão insegura têm superfícies próprias.

### O que deve ser melhorado no nosso desenho

- Evitar hamburger como único acesso a funções importantes; usar top bar compacta e menu de overflow.
- Não depender do visual genérico do Ionic/Material.
- Usar feedback mais discreto que escala 0.9; no Android, 0.96–0.97 preserva precisão visual e reduz movimento.

## 2.4 Síntese

O redesign deve combinar:

- **Macro Deck:** estrutura, estados, grade consistente, separação entre uso e administração;
- **WebDeck:** personalização, aproveitamento do canvas, fundos e variedade de conteúdo;
- **Android nativo:** Material 3 adaptativo, acessibilidade, navegação previsível, haptics e integração com arquivos.

Não serão copiados códigos, ícones, imagens ou recursos das referências. WebDeck é GPL-3.0 e Macro Deck é Apache-2.0; serão usados apenas padrões abstratos de UX observados publicamente.

---

## 3. Direção de arte proposta — “Command Surface”

### 3.1 Conceito

Uma superfície de comando escura, precisa e discreta, inspirada em hardware profissional. A interface administrativa deve desaparecer durante o uso; ícones, cor e feedback das teclas são os protagonistas. O visual precisa parecer um produto dedicado, não um formulário Android.

### 3.2 Paleta dark principal

| Token | HEX | Uso |
|---|---:|---|
| `Obsidian` | `#090C12` | fundo principal |
| `Graphite` | `#111722` | superfícies e top bar |
| `Slate` | `#182131` | cartões elevados e campos |
| `Steel` | `#273247` | bordas e divisores |
| `Mist` | `#F5F7FA` | texto principal |
| `Ash` | `#98A2B3` | texto secundário |
| `Pulse` | `#38D9C5` | marca, foco e ação primária |
| `Pulse Dark` | `#20B8A6` | estado pressionado |
| `Success` | `#42D17B` | concluído/conectado |
| `Warning` | `#FFB648` | atenção/reconexão |
| `Danger` | `#FF5D73` | erro/remoção |
| `Info` | `#5AA7FF` | sincronização/informação |

### 3.3 Tema claro secundário

Disponibilizar tema claro, mas manter dark como padrão do produto:

- fundo `#F3F6FA`;
- superfície `#FFFFFF`;
- superfície elevada `#E9EEF5`;
- borda `#CDD6E3`;
- texto `#121722`;
- acento `#007F73`.

### 3.4 Tipografia

- **Família:** Inter, empacotada em `res/font` sob licença OFL; fallback `sans-serif`.
- **Display do deck:** 20–24sp, 700.
- **Títulos de tela:** 22sp, 650–700.
- **Rótulo de tecla:** 12–14sp, 600, máximo de duas linhas.
- **Corpo:** 14–16sp, 400–500.
- **Metadados:** 11–12sp, 500, com números tabulares quando necessário.
- Não usar texto menor que 11sp nem depender apenas de caixa alta.

### 3.5 Formas, espaçamento e elevação

- escala de espaçamento: 4, 8, 12, 16, 24 e 32dp;
- raio das teclas: 18% do lado, limitado entre 12 e 24dp;
- raio dos cartões: 16dp;
- raio de chips/campos: 12dp;
- borda padrão: 1dp; foco: 2dp;
- sombra mínima; separar superfícies por tom e borda, não por elevações pesadas.

### 3.6 Iconografia

- Material Symbols Rounded/ícones vetoriais como base.
- Catálogo fechado mapeando IDs do protocolo para `ImageVector`.
- Fallback consistente: ícone de comando, nunca `●` Unicode.
- Ícones de usuário opcionais via URI/arquivo em fase posterior; nunca reutilizar assets das referências.

### 3.7 Movimento e haptics

- press: escala `1.0 → 0.96` em 70ms;
- release: retorno em 140ms com easing suave;
- execução: anel fino de progresso sobre a tecla, sem desmontar o conteúdo;
- sucesso: flash de borda verde por 450ms;
- erro: borda vermelha e vibração curta de erro;
- troca de página: fade/slide de 180ms;
- respeitar `ANIMATOR_DURATION_SCALE=0` e preferência de movimento reduzido;
- haptic leve no press e confirmação distinta quando o ACK chega.

---

## 4. Arquitetura de navegação proposta

### Destinos

1. `Pairing` — onboarding/pareamento;
2. `Deck` — destino principal e tela cheia;
3. `Editor` — edição contextual de uma tecla/página;
4. `Profiles` — lista de perfis;
5. `ProfileDetail` — páginas e ações de um perfil;
6. `Transfer` — importar/exportar;
7. `Settings` — aparência, conexão e informações.

### Regras

- Não usar bottom navigation: o deck precisa de área máxima e há apenas um destino de uso frequente.
- No deck, usar top app bar compacta com perfil, página, status e overflow.
- Administração fica no overflow e em ações contextuais; edição entra por botão “Editar” ou long press opcional.
- Back fecha sheets/diálogos, retorna do detalhe à lista e do editor ao deck preservando draft.
- Estado de conexão não deve decidir a estrutura inteira da UI; deck offline continua visível, mas desabilitado e com ação de reconexão.

---

## 5. Redesign por tela

## 5.1 Pareamento e primeiro uso

### Etapa 1 — Boas-vindas

- marca, ilustração abstrata de grid e texto curto;
- ações “Conectar ao computador” e “Usar configuração salva”, quando aplicável;
- benefícios resumidos, sem detalhes de protocolo.

### Etapa 2 — Servidor

- lista de conexões salvas/disponíveis quando existir descoberta;
- modo manual com endereço e nome deste dispositivo;
- QR code fica explicitamente fora do escopo enquanto o servidor não oferecer bundle seguro compatível;
- configuração TLS avançada recolhida em uma seção “Segurança da conexão”.

### Etapa 3 — Confiança e código

- CA PEM em campo monoespaçado expansível, não ocupando a tela inicialmente;
- código de confiança formatado em grupos e apresentado como verificação visual;
- código de pareamento separado;
- resumo “Conexão HTTPS privada / identidade verificada”.

### Estados

- conectando: modal/surface com etapas (`Validando certificado`, `Pareando`, `Sincronizando perfil`);
- sucesso: check, nome do perfil e CTA “Abrir meu deck”;
- erro: mensagem segura, causa acionável e opções “Tentar novamente”/“Editar dados”;
- pareamento já salvo: reconexão automática sem exibir o formulário.

## 5.2 Deck principal

### Top bar compacta

- esquerda: nome do perfil;
- centro ou linha secundária: seletor de página em chips/pager;
- direita: ponto de status e menu de overflow;
- status detalhado abre bottom sheet; não ocupa três linhas permanentes.

### Grade

- preservar `rows × columns` do servidor;
- preencher a maior área possível mantendo células quadradas;
- compact: gap 8dp; medium/expanded: 10–12dp;
- se a grade lógica não couber com alvo aceitável, permitir rolagem ou sugerir paisagem, sem reordenar posições;
- células vazias ficam transparentes no modo normal;
- no modo edição, células vazias recebem contorno tracejado e ícone `+`.

### Tecla

Camadas:

1. background de cor segura/gradiente sutil;
2. ícone central;
3. label no rodapé com scrim para legibilidade;
4. badges opcionais (tipo de ação, estado, pasta);
5. overlay de execução/erro.

Regras:

- contraste do conteúdo calculado por luminância;
- título máximo de duas linhas;
- toque mínimo de 56dp; alvo preferencial de 72–96dp;
- `contentDescription` combina título, tipo e estado;
- pressionar não navega nem abre administração acidentalmente.

### Ações administrativas

- “Editar deck”, “Gerenciar perfis”, “Reconectar”, “Configurações” e “Remover pareamento” no overflow/bottom sheet;
- remover os três `OutlinedButton` de largura total do rodapé.

## 5.3 Editor contextual

### Estrutura

- top bar com fechar, título e salvar fixo;
- preview vivo da tecla no topo;
- grid miniatura para selecionar/mover a tecla;
- abas ou seções: `Aparência`, `Ação`, `Posição`;
- alterações mantidas localmente até salvar.

### Aparência

- título;
- seletor visual de ícone pesquisável;
- paleta de swatches + seletor de cor avançado;
- preview automático de contraste;
- opção de remover customização e voltar ao tema.

### Ação

- cards de tipos: Atalho, Tecla, Mídia, Texto, URL, Aplicativo;
- formulários específicos por tipo;
- modificadores como chips selecionáveis (`Ctrl`, `Alt`, `Shift`, `Win`);
- mídia como lista com ícones e rótulos em PT-BR;
- aplicação como catálogo fechado, preservando o modelo fail-closed;
- nunca expor caminho arbitrário de executável.

### Posição

- seleção espacial na mini-grade;
- linha/coluna apenas em “Avançado”;
- posição ocupada exige troca ou cancelamento explícito.

### Erros e recuperação

- erro por campo próximo ao campo;
- conflito de revisão em diálogo com “Recarregar versão do servidor”, “Tentar salvar novamente” e “Cancelar”;
- “Reverter alterações” no menu ou banner de falha, não como botão solto no fluxo normal.

## 5.4 Perfis e páginas

### Lista de perfis

- cards com nome, badge `Ativo`, quantidade de páginas e revisão em metadado discreto;
- toque abre detalhes;
- menu contextual: ativar, renomear, duplicar, exportar, excluir;
- FAB “Novo perfil” ou botão de estado vazio;
- IDs internos ficam em detalhes avançados.

### Detalhe do perfil

- cabeçalho com nome, estado e ação “Ativar”;
- lista ordenada de páginas com drag handle quando suportado;
- ações por página: abrir, renomear, duplicar, mover e excluir;
- criar página por diálogo curto;
- exclusão de perfil/página ativa solicita substituto por seletor, não por campo de ID.

### Importação/exportação

- usar Android Storage Access Framework para escolher/criar `.json`;
- mostrar nome, tamanho e validação do arquivo;
- preview com nome do perfil, páginas e quantidade de botões;
- confirmação antes de sobrescrever;
- JSON bruto apenas em opção de diagnóstico, fora do fluxo principal.

## 5.5 Configurações

Seções:

- Aparência: tema do sistema/claro/escuro, intensidade de haptic, movimento reduzido;
- Deck: manter tela ativa, orientação, mostrar rótulos, densidade visual;
- Conexão: servidor atual, status TLS, reconectar, remover pareamento;
- Sobre: versão, licenças e documentação.

Diagnóstico técnico não deve ficar na navegação principal.

## 5.6 Estados globais

Criar componentes dedicados para:

- loading/skeleton;
- vazio;
- offline;
- conexão perdida;
- erro recuperável;
- erro não recuperável;
- sucesso transitório;
- conflito de revisão;
- ação executando/concluída/rejeitada;
- perfil sem páginas ou página sem botões.

---

## 6. Responsividade

### Compacto: `< 600dp`

- telefone em retrato;
- top bar de uma linha e seletor de página horizontal;
- formulários em uma coluna;
- editor em tela inteira;
- ações secundárias em bottom sheet.

### Médio: `600–839dp`

- tablets pequenos/paisagem;
- deck + painel contextual opcional;
- editor em duas colunas: preview/grid e propriedades;
- perfis em lista com painel de detalhe.

### Expandido: `≥ 840dp`

- tablets grandes;
- shell com rail administrativo opcional fora do modo deck;
- master-detail para perfis;
- grid centralizado, sem esticar teclas além do limite útil.

### Compatibilidade

- Galaxy A10 permanece alvo posterior; não presumir densidade/resolução sem validação física;
- validar primeiro em emulador compacto e tablet;
- suportar retrato e paisagem sem alterar a ordem lógica da grade;
- fonte em 1.0×, 1.3× e 2.0× sem corte das ações essenciais.

---

## 7. Estrutura de código planejada

### Criar

```text
android/app/src/main/java/br/com/gustavo/streamdeck/ui/theme/
  Color.kt
  Shape.kt
  Spacing.kt
  Theme.kt
  Type.kt

android/app/src/main/java/br/com/gustavo/streamdeck/ui/navigation/
  StreamDeckDestination.kt
  StreamDeckNavigator.kt

android/app/src/main/java/br/com/gustavo/streamdeck/ui/components/
  CommandTopBar.kt
  ConnectionIndicator.kt
  FeedbackBanner.kt
  LoadingState.kt
  EmptyState.kt
  ConfirmDialog.kt
  SectionCard.kt

android/app/src/main/java/br/com/gustavo/streamdeck/ui/deck/
  DeckScreen.kt
  DeckGrid.kt
  CommandKey.kt
  PageSelector.kt
  DeckOverflowMenu.kt

android/app/src/main/java/br/com/gustavo/streamdeck/ui/pairing/
  PairingScreen.kt
  PairingStep.kt
  PairingSecuritySection.kt
  PairingProgress.kt

android/app/src/main/java/br/com/gustavo/streamdeck/ui/editor/
  EditorScreen.kt
  ButtonPreview.kt
  ButtonPickerGrid.kt
  AppearanceEditor.kt
  ActionEditor.kt
  PositionEditor.kt
  IconCatalog.kt

android/app/src/main/java/br/com/gustavo/streamdeck/ui/profiles/
  ProfilesScreen.kt
  ProfileCard.kt
  ProfileDetailScreen.kt
  PageRow.kt
  ProfileDialogs.kt
  TransferScreen.kt

android/app/src/main/java/br/com/gustavo/streamdeck/ui/settings/
  SettingsScreen.kt

android/app/src/main/res/font/
  inter_regular.ttf
  inter_medium.ttf
  inter_semibold.ttf
  inter_bold.ttf
```

### Modificar

- `android/app/src/main/java/br/com/gustavo/streamdeck/App.kt` — manter orquestração inicialmente; extrair renderização e depois estado por feature.
- `android/app/src/main/java/br/com/gustavo/streamdeck/MainActivity.kt` — edge-to-edge, tema e comportamento de orientação/insets.
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/StreamDeckGrid.kt` — substituir progressivamente por `ui/deck/DeckGrid.kt`.
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/ProfileEditorScreen.kt` — migrar para subcomponentes do editor.
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/ProfileManagementScreen.kt` — substituir por lista/detalhe/transferência.
- `android/app/src/main/res/values/strings.xml` — mover todo texto visível e adicionar PT-BR consistente.
- `android/app/src/main/res/values/themes.xml` — usar tema edge-to-edge sem barras claras fixas.
- `android/app/build.gradle.kts` — adicionar apenas dependências efetivamente necessárias; preferir vetores e APIs Compose já presentes.

### Preservar

- contratos `ServerEndpoint`, `TlsTrust`, `PairingClient` e `StreamDeckWebSocketClient`;
- armazenamento criptografado de pareamento;
- HTTPS/WSS obrigatório;
- catálogo fechado para `application`;
- revisão otimista e escolhas explícitas de conflito;
- posição lógica de botões e páginas recebidas do servidor.

---

## 8. Plano de implementação por slices

## Slice 0 — Congelar contrato visual e inventário

**Objetivo:** evitar redesign improvisado e regressões de escopo.

1. Criar `docs/design/android-streamdeck-design-system.md` com tokens finais, exemplos e regras.
2. Criar matriz tela × estado × tamanho de janela.
3. Registrar capturas do estado anterior quando a validação visual for reautorizada.
4. Confirmar que nenhuma funcionalidade/protocolo será removida.
5. Commit sugerido: `docs: define Android StreamDeck redesign system`.

## Slice 1 — Fundação visual

**Objetivo:** aplicar identidade sem mudar fluxos.

1. Criar tema, cores, tipografia, formas e spacing.
2. Aplicar edge-to-edge e barras de sistema coerentes.
3. Substituir Unicode por catálogo de ícones vetoriais.
4. Criar banners, indicadores e estados base.
5. Adicionar previews Compose para dark/light e escalas de fonte.
6. Commit sugerido: `feat(android): add Command Surface design system`.

## Slice 2 — Shell e deck principal

**Objetivo:** fazer a tarefa principal parecer um produto dedicado.

1. Criar destinos explícitos e shell.
2. Implementar top bar compacta, status e overflow.
3. Implementar `CommandKey` em camadas e feedback de press/ACK.
4. Tornar células vazias invisíveis fora da edição.
5. Implementar seletor de páginas e comportamento adaptativo.
6. Remover botões administrativos do rodapé.
7. Commit sugerido: `feat(android): redesign deck command surface`.

## Slice 3 — Pareamento

**Objetivo:** reduzir carga cognitiva sem enfraquecer TLS.

1. Converter formulário em fluxo de etapas.
2. Recolher configuração avançada, mantendo CA e trust code obrigatórios.
3. Criar estados de conexão, sucesso e falha dedicados.
4. Reutilizar credencial salva e oferecer reconexão clara.
5. Não implementar QR sem contrato seguro do servidor.
6. Commit sugerido: `feat(android): redesign secure pairing flow`.

## Slice 4 — Editor visual

**Objetivo:** substituir o formulário técnico por edição contextual.

1. Criar preview vivo e seleção na mini-grade.
2. Separar aparência, ação e posição.
3. Implementar catálogo de ícones, swatches e contraste automático.
4. Trocar ciclos de tipo/comando por seletores explícitos.
5. Manter `application` em catálogo fechado.
6. Fixar salvar/cancelar fora da área coberta pelo teclado.
7. Commit sugerido: `feat(android): add visual command editor`.

## Slice 5 — Perfis, páginas e transferência

**Objetivo:** transformar gerenciamento técnico em master-detail claro.

1. Criar lista de perfis e estado vazio.
2. Criar detalhe com páginas ordenadas e menus contextuais.
3. Mover CRUD para diálogos focados.
4. Traduzir conflitos para decisões orientadas ao usuário.
5. Migrar import/export para arquivo com preview seguro.
6. Commit sugerido: `feat(android): redesign profile management`.

## Slice 6 — Configurações e estados globais

**Objetivo:** completar coerência em todos os caminhos.

1. Criar configurações de aparência/deck/conexão/sobre.
2. Implementar offline sem esconder o deck.
3. Implementar loading, empty, success, error e conflito consistentes.
4. Adicionar preferências de movimento e haptics.
5. Commit sugerido: `feat(android): complete settings and global states`.

## Slice 7 — Acessibilidade, adaptação e polimento

**Objetivo:** tornar o redesign utilizável em diferentes dispositivos e capacidades.

1. Auditar contraste e luminância de cores customizadas.
2. Garantir alvos mínimos e ordem de foco.
3. Verificar TalkBack/semântica dos botões e estados.
4. Verificar fonte ampliada e telas compactas/médias/expandidas.
5. Refinar animações e reduzir movimento quando configurado.
6. Commit sugerido: `fix(android): polish adaptive and accessible UI`.

## Slice 8 — Validação visual e publicação

**Objetivo:** provar o resultado final com artefato real.

> Bloqueado enquanto Gustavo mantiver a ordem de cancelar testes.

Quando reautorizado:

1. Executar testes unitários, lint e assemble em comandos separados.
2. Gerar APK final e instalar esse artefato no emulador.
3. Validar fluxos de pareamento, deck, editor, perfis, conflito e offline.
4. Capturar screenshots em compacto retrato/paisagem e tablet.
5. Inspecionar hierarquia UiAutomator e contraste.
6. Comparar com baseline e revisar inconsistências.
7. Atualizar changelog/release notes.
8. Commit, push, SHA remoto e CI verde.

---

## 9. Estratégia de validação futura

Nenhum comando abaixo deve ser executado sem nova autorização.

### Testes unitários planejados

- tokens e contraste;
- mapeamento fechado de ícones;
- cálculo adaptativo da grade;
- destinos e back navigation;
- estado do editor preservado;
- tradução de conflitos;
- preferência de tema/movimento.

### Testes Compose planejados

- tecla em todos os estados;
- deck com células vazias, títulos longos e cores extremas;
- pairing em cada etapa e erro;
- editor com teclado aberto;
- perfil vazio, lista populada e conflito;
- fonte 2.0× e largura compacta.

### Gates futuros

```bash
./gradlew :app:testDebugUnitTest
./gradlew :app:lintDebug
./gradlew :app:assembleDebug
./gradlew :app:assembleDebugAndroidTest
./gradlew :app:connectedDebugAndroidTest
```

Registrar resultados separadamente; não considerar build como prova de qualidade visual.

### Validação visual manual futura

- emulador compacto em retrato e paisagem;
- emulador tablet;
- screenshots dark/light;
- TalkBack/UiAutomator;
- Galaxy A10 somente depois, como validação física de compatibilidade;
- confirmar que o APK testado é exatamente o APK final.

---

## 10. Critérios de aceite do redesign

### Identidade

- [ ] Nenhuma tela principal aparenta usar Material 3 sem customização.
- [ ] Dark e light usam os mesmos tokens sem cores arbitrárias locais.
- [ ] Todos os ícones são vetoriais/recursos controlados; nenhum glyph Unicode permanece.
- [ ] Tipografia, formas e spacing são consistentes de ponta a ponta.

### Deck

- [ ] Grade ocupa a maior parte da tela.
- [ ] Posição lógica de todas as teclas é preservada.
- [ ] Células vazias não poluem o modo normal.
- [ ] Press, execução, sucesso e erro são reconhecíveis sem depender apenas de cor.
- [ ] Ações administrativas não competem com as teclas.

### Pareamento

- [ ] Segurança TLS permanece fail-closed.
- [ ] Usuário não enfrenta todos os campos técnicos simultaneamente.
- [ ] Conectando, sucesso e erro possuem ações claras.
- [ ] Credencial salva reconecta sem repetir configuração.

### Editor

- [ ] Usuário vê preview antes de salvar.
- [ ] Ícone, cor e tipo de ação são escolhidos visualmente.
- [ ] Salvar/cancelar continuam acessíveis com teclado aberto.
- [ ] Conflito e recuperação usam PT-BR e decisões compreensíveis.

### Perfis

- [ ] CRUD é dividido em lista, detalhe e diálogos.
- [ ] IDs/revisões ficam secundários.
- [ ] Exclusões exigem confirmação e substituição explícita quando necessária.
- [ ] Import/export usa arquivo e preview, sem JSON bruto no fluxo principal.

### Acessibilidade e adaptação

- [ ] Contraste atende WCAG AA para texto/controles relevantes.
- [ ] TalkBack anuncia título, tipo, estado e ação.
- [ ] Interface continua operável com fonte 2.0×.
- [ ] Compacto, paisagem e tablet não cortam ações essenciais.
- [ ] Movimento reduzido e haptics são respeitados.

### Segurança e regressão

- [ ] Nenhum downgrade para HTTP/WS.
- [ ] Nenhuma credencial, CA privada sensível ou token aparece em logs/UI pública.
- [ ] `application` continua aceitando apenas IDs do catálogo.
- [ ] Revisão otimista e conflito explícito continuam preservados.
- [ ] Nenhum código ou asset de WebDeck/Macro Deck foi incorporado.

---

## 11. Fora do escopo desta fase

- sistema de plugins;
- loja de extensões/icon packs;
- GIFs animados;
- widgets de CPU/GPU/RAM;
- editor desktop;
- QR code sem protocolo seguro definido;
- caminhos arbitrários para executáveis;
- redesenho do protocolo ou remoção de garantias TLS;
- assinatura de produção sem keystore externo real.

Esses itens podem ser avaliados depois do núcleo visual estar coeso e validado.

---

## 12. Resultado esperado

Ao final, o app deve abrir diretamente em uma superfície de comando limpa e escura, com teclas visuais grandes, status discreto, feedback imediato e administração fora do caminho principal. Pareamento, edição e perfis devem parecer partes do mesmo produto, não formulários independentes. A experiência deve preservar toda a segurança atual e funcionar do telefone compacto ao tablet sem alterar a lógica recebida do servidor.

---

## 13. Execução registrada — 2026-08-11

### Implementado

- Fundação visual `Command Surface` em Compose:
  - paleta escura/grafite com acento Pulse;
  - tema claro e escuro;
  - tipografia Inter variável empacotada sob OFL;
  - tokens de espaçamento, formas e tipografia;
  - tema Android compatível com API 26 e variant API 27 para navegação.
- Deck operacional:
  - top bar compacta com perfil, página, revisão e status;
  - menu contextual para edição, gerenciamento e limpeza do pareamento;
  - teclas com ícones vetoriais, contraste adaptativo, elevação, escala ao pressionar e estados de execução;
  - células vazias sem peso visual desnecessário;
  - sem alteração do protocolo HTTPS/WSS ou do catálogo de aplicações.
- Pareamento:
  - cartão de identidade do produto;
  - etapas visuais para conexão e segurança;
  - CA PEM/código de confiança em seção expansível;
  - progresso, erro e estado de conexão visíveis;
  - callbacks e validações existentes preservados.
- Editor:
  - preview vivo da tecla;
  - seleção visual de tecla;
  - cartões de aparência, ação e posição;
  - ícones e cores selecionáveis;
  - barra fixa de cancelar/salvar;
  - undo/recovery e contratos de validação preservados;
  - haptics no pressionamento das teclas;
  - seletor nativo de arquivo JSON para importação e exportação.
- Gestão:
  - perfis e páginas agrupados em cartões;
  - ativo, revisão e IDs em hierarquia secundária;
  - operações de conflito, import/export e exclusão explicitamente sinalizadas;
  - parâmetros dos callbacks existentes preservados.
- Correção estrutural necessária para compilação: declaração de `ButtonExecutionState`, que já era importada pelo app mas não existia no checkout.

### Arquivos principais alterados/criados

- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/theme/Color.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/theme/Spacing.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/theme/Shape.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/theme/Type.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/theme/Theme.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/components/ConnectionIndicator.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/navigation/StreamDeckDestination.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/ButtonExecutionState.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/StreamDeckGrid.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/ProfileEditorScreen.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/ui/ProfileManagementScreen.kt`
- `android/app/src/main/java/br/com/gustavo/streamdeck/App.kt`
- `android/app/src/main/res/font/inter_variable.ttf`
- `android/app/src/main/res/values/themes.xml`
- `android/app/src/main/res/values-v27/themes.xml`
- `android/app/build.gradle.kts`
- `docs/licenses/Inter-OFL.txt`

### Validação executada

Executado no diretório `android/` com Temurin JDK 21.0.12:

- `./gradlew :app:assembleDebug :app:testDebugUnitTest` — **BUILD SUCCESSFUL**;
- `./gradlew :app:lintDebug :app:assembleDebugAndroidTest` — **BUILD SUCCESSFUL**, lint sem erros;
- `./gradlew :app:testDebugUnitTest :app:assembleDebug` — **BUILD SUCCESSFUL**;
- APK debug: `android/app/build/outputs/apk/debug/app-debug.apk`, `22.345.868` bytes;
- APK de testes: `android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk`, `440.420` bytes;
- `git diff --check` — sem erros de whitespace.

### Ainda pendente

- extração completa do shell de `App.kt` para módulos `deck/pairing/editor/profiles`;
- tela `Settings` persistente para tema, densidade, movimento reduzido e intensidade de haptic;
- seletor/pager de páginas quando o contrato de estado ativo permitir a troca no cliente;
- preview/validação de metadados e confirmação de sobrescrita no fluxo SAF;
- estado de edição com contorno para células vazias e componentes dedicados de confirmação;
- validação visual/interativa no emulador ou Galaxy A10;
- screenshots/golden tests;
- instrumentação E2E (`connectedDebugAndroidTest`);
- assinatura de produção;
- commit, push e CI remoto.

Esses itens não são declarados como concluídos nesta execução.
