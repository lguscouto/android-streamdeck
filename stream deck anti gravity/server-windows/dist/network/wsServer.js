"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WsServer = void 0;
const ws_1 = require("ws");
const protocol_1 = require("../protocol");
class WsServer {
    wss = null;
    port;
    profileStore;
    engine;
    connectedClientsCount = 0;
    constructor(port = 5001, profileStore, engine) {
        this.port = port;
        this.profileStore = profileStore;
        this.engine = engine;
        // Registrar callbacks do engine para notificar todos os clientes conectados
        this.engine.registerStateChangeHandler((buttonId, newState) => {
            this.broadcast({
                event: protocol_1.EventTypes.BUTTON_STATE_CHANGE,
                payload: { buttonId, newState }
            });
        });
        this.engine.registerGridSyncHandler(() => {
            this.broadcastGridSync();
        });
    }
    start() {
        this.wss = new ws_1.WebSocketServer({ port: this.port });
        console.log(`[WsServer] Servidor WebSocket Multi-Dispositivo rodando na porta ${this.port}`);
        this.wss.on('connection', (ws) => {
            this.connectedClientsCount++;
            console.log(`[WsServer] Novo cliente conectado! Dispositivos ativos: ${this.connectedClientsCount}`);
            // Enviar sincronização inicial da grade para o novo dispositivo
            this.sendGridSync(ws);
            ws.on('message', (raw) => {
                try {
                    const message = JSON.parse(raw.toString());
                    this.handleMessage(ws, message);
                }
                catch (err) {
                    console.error('[WsServer] Erro ao processar mensagem JSON do cliente:', err);
                }
            });
            ws.on('close', () => {
                this.connectedClientsCount = Math.max(0, this.connectedClientsCount - 1);
                console.log(`[WsServer] Cliente desconectado. Dispositivos ativos restantes: ${this.connectedClientsCount}`);
            });
        });
    }
    handleMessage(ws, message) {
        switch (message.event) {
            case protocol_1.EventTypes.PING:
                ws.send(JSON.stringify({
                    event: protocol_1.EventTypes.PONG,
                    payload: {
                        clientTimestamp: message.payload?.timestamp,
                        serverTimestamp: Date.now()
                    }
                }));
                break;
            case protocol_1.EventTypes.PRESS_BUTTON:
                this.engine.handlePressButton(message.payload);
                break;
            case protocol_1.EventTypes.SWITCH_PAGE:
                this.engine.handleSwitchPage(message.payload);
                break;
            default:
                console.log(`[WsServer] Evento não mapeado: ${message.event}`);
                break;
        }
    }
    sendGridSync(ws) {
        const profile = this.profileStore.getActiveProfile();
        const config = this.profileStore.getConfig();
        const payload = {
            activeProfileId: config.activeProfileId,
            activePageIndex: config.activePageIndex,
            gridConfig: profile ? profile.gridConfig : { rows: 3, cols: 4 },
            buttons: this.profileStore.getActivePageButtons()
        };
        if (ws.readyState === ws_1.WebSocket.OPEN) {
            ws.send(JSON.stringify({
                event: protocol_1.EventTypes.GRID_SYNC,
                payload
            }));
        }
    }
    broadcastGridSync() {
        const profile = this.profileStore.getActiveProfile();
        const config = this.profileStore.getConfig();
        const payload = {
            activeProfileId: config.activeProfileId,
            activePageIndex: config.activePageIndex,
            gridConfig: profile ? profile.gridConfig : { rows: 3, cols: 4 },
            buttons: this.profileStore.getActivePageButtons()
        };
        this.broadcast({
            event: protocol_1.EventTypes.GRID_SYNC,
            payload
        });
    }
    broadcast(message) {
        if (!this.wss)
            return;
        const json = JSON.stringify(message);
        this.wss.clients.forEach((client) => {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send(json);
            }
        });
    }
    getConnectedClientsCount() {
        return this.connectedClientsCount;
    }
}
exports.WsServer = WsServer;
