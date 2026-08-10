# 🎮 AntiGravity Stream Deck V2

> Transforme seu smartphone Android em um **Stream Deck** profissional para Windows — com temas visuais premium, monitores de hardware em tempo real, integração com Spotify e Discord, macros em cadeia e suporte a múltiplos dispositivos simultâneos.

---

## ✨ Funcionalidades V2

| Funcionalidade | Descrição |
|---|---|
| 🎨 **Design System Premium** | 4 temas visuais: Cyberpunk Neon, OLED Dark, Glassmorphism, Nordic Slate |
| 🖼️ **Ícones Animados** | Suporte a GIF, WEBP e SVG nos botões |
| 📐 **Botões Dinâmicos** | Tamanhos variáveis (`colSpan`/`rowSpan`) e pastas de sub-deck |
| 🖥️ **Monitor de Hardware** | CPU %, CPU °C, RAM GB, GPU % em tempo real |
| 🎵 **Integração Spotify** | Exibe faixa atual e controla play/pause |
| 🎮 **Integração Discord** | Mute e Deafen via hotkeys globais |
| ⚡ **Macros em Cadeia** | Sequenciador multi-ação com delay configurável |
| 🖱️ **Drag & Drop Visual** | Reorganize botões arrastando no Editor Web |
| 📱 **Multi-Device** | Vários celulares/tablets conectados simultaneamente |

---

## 🚀 Início Rápido

### Pré-requisitos
- **Node.js** 18+ ([nodejs.org](https://nodejs.org))
- **Windows** 10/11 (x64)
- **Android** 8.0+ (para o app cliente)

### Instalação do Servidor (Windows)

```bash
# 1. Instalar dependências
cd server-windows
npm install

# 2. Compilar TypeScript
npm run build

# 3. Iniciar o servidor (ou use o atalho abaixo)
npm start
```

**Ou simplesmente clique duas vezes em `start-server.bat`** para iniciar com um único clique!

### Instalação do App Android

1. Instale o APK: `client-android/app/build/outputs/apk/debug/app-debug.apk`
2. Conecte o Android **ao mesmo Wi-Fi** do PC
3. Abra o app, insira o IP do PC e porta `5001`
4. Toque em **Conectar** ✅

---

## 🎛️ Editor Web de Botões

Acesse `http://localhost:5000` no navegador para:
- Criar e editar botões por linha/coluna
- Configurar ações (teclas de atalho, apps, mídia, etc.)
- Trocar temas visuais ao vivo
- Arrastar e soltar para reorganizar botões
- Monitorar hardware em widgets dedicados

---

## 📡 Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                 AntiGravity Stream Deck V2               │
├─────────────────────────────────────────────────────────┤
│   [Android App]  ◄──── WebSocket :5001 ────►  [Server]  │
│   [Tablet / TV]  ◄──── WebSocket :5001 ────►  [Windows] │
│   [Web Editor]   ◄──── HTTP REST  :5000 ────►  [Engine] │
└─────────────────────────────────────────────────────────┘
```

### Módulos do Servidor

| Módulo | Arquivo | Função |
|---|---|---|
| Engine | `src/core/engine.ts` | Processa ações dos botões |
| WsServer | `src/network/wsServer.ts` | WebSocket multi-dispositivo |
| HttpServer | `src/network/httpServer.ts` | API REST + Editor Web |
| HardwareMonitor | `src/native/hardwareMonitor.ts` | CPU/RAM/GPU em tempo real |
| SpotifyController | `src/native/spotifyController.ts` | Integração Spotify |
| DiscordController | `src/native/discordController.ts` | Mute/Deafen Discord |
| KeyboardController | `src/native/keyboardController.ts` | Envio de teclas/hotkeys |
| AudioController | `src/native/audioController.ts` | Controle de volume/mute |
| AppLauncher | `src/native/appLauncher.ts` | Lançar apps e URLs |
| ObsController | `src/native/obsController.ts` | Integração OBS Studio |

---

## 🎯 Tipos de Ação Disponíveis

```
HOTKEY           → Atalho de teclado (ex: Ctrl+C)
MEDIA_PLAY_PAUSE → Play/Pause mídia global
MEDIA_NEXT       → Próxima faixa
MEDIA_PREV       → Faixa anterior
VOLUME_MUTE      → Mute/Unmute do sistema
VOLUME_UP        → Aumentar volume
VOLUME_DOWN      → Diminuir volume
LAUNCH_APP       → Abrir aplicativo
OPEN_URL         → Abrir URL no navegador
OPEN_FOLDER      → Abrir sub-deck de pastas
OBS_SET_SCENE    → Trocar cena no OBS Studio
HW_CPU           → Widget: uso e temperatura CPU
HW_RAM           → Widget: uso de memória RAM
HW_GPU           → Widget: uso da GPU
SPOTIFY_TRACK    → Widget: faixa atual do Spotify
DISCORD_TOGGLE_MUTE   → Alternar mute no Discord
DISCORD_TOGGLE_DEAFEN → Alternar deafen no Discord
MULTI_ACTION     → Sequência de múltiplas ações
```

---

## 🔧 Desenvolvimento

```bash
# Modo desenvolvimento (hot-reload)
cd server-windows
npm run dev

# Build de produção
npm run build
npm start
```

---

## 📋 Changelog V2

### V2.0 (Fase 10-20)
- ✅ Design System com 4 temas premium
- ✅ Suporte a ícones GIF/WEBP animados
- ✅ Botões de tamanhos variáveis e pastas
- ✅ Monitor de hardware em tempo real (systeminformation)
- ✅ Integração Spotify (título da faixa + status)
- ✅ Integração Discord (Mute/Deafen)
- ✅ Sequenciador de macros em cadeia (MULTI_ACTION)
- ✅ Drag & Drop no Editor Web
- ✅ Suporte multi-device simultâneo

### V1.0 (Release Inicial)
- ✅ Comunicação WebSocket Android ↔ Windows
- ✅ Editor Web de botões
- ✅ Controle de teclado, volume e mídia
- ✅ Integração básica com OBS Studio
- ✅ Sistema de perfis persistentes

---

## 📄 Licença

MIT © AntiGravity
