import { WebSocketServer, WebSocket } from 'ws';
import { ProfileStore } from '../config/profileStore';
import { Engine } from '../core/engine';
import {
  EventTypes,
  GridSyncPayload,
  PressButtonPayload,
  WebSocketMessage
} from '../protocol';

export class WsServer {
  private wss: WebSocketServer | null = null;
  private port: number;
  private profileStore: ProfileStore;
  private engine: Engine;
  private connectedClientsCount: number = 0;

  constructor(port: number = 5001, profileStore: ProfileStore, engine: Engine) {
    this.port = port;
    this.profileStore = profileStore;
    this.engine = engine;

    // Registrar callbacks do engine para notificar todos os clientes conectados
    this.engine.registerStateChangeHandler((buttonId, newState) => {
      this.broadcast({
        event: EventTypes.BUTTON_STATE_CHANGE,
        payload: { buttonId, newState }
      });
    });

    this.engine.registerGridSyncHandler(() => {
      this.broadcastGridSync();
    });
  }

  public start(): void {
    this.wss = new WebSocketServer({ port: this.port });
    console.log(`[WsServer] Servidor WebSocket Multi-Dispositivo rodando na porta ${this.port}`);

    this.wss.on('connection', (ws: WebSocket) => {
      this.connectedClientsCount++;
      console.log(`[WsServer] Novo cliente conectado! Dispositivos ativos: ${this.connectedClientsCount}`);

      // Enviar sincronização inicial da grade para o novo dispositivo
      this.sendGridSync(ws);

      ws.on('message', (raw: string) => {
        try {
          const message: WebSocketMessage = JSON.parse(raw.toString());
          this.handleMessage(ws, message);
        } catch (err) {
          console.error('[WsServer] Erro ao processar mensagem JSON do cliente:', err);
        }
      });

      ws.on('close', () => {
        this.connectedClientsCount = Math.max(0, this.connectedClientsCount - 1);
        console.log(`[WsServer] Cliente desconectado. Dispositivos ativos restantes: ${this.connectedClientsCount}`);
      });
    });
  }

  private handleMessage(ws: WebSocket, message: WebSocketMessage): void {
    switch (message.event) {
      case EventTypes.PING:
        ws.send(
          JSON.stringify({
            event: EventTypes.PONG,
            payload: {
              clientTimestamp: message.payload?.timestamp,
              serverTimestamp: Date.now()
            }
          })
        );
        break;

      case EventTypes.PRESS_BUTTON:
        this.engine.handlePressButton(message.payload as PressButtonPayload);
        break;

      case EventTypes.SWITCH_PAGE:
        this.engine.handleSwitchPage(message.payload);
        break;

      default:
        console.log(`[WsServer] Evento não mapeado: ${message.event}`);
        break;
    }
  }

  public sendGridSync(ws: WebSocket): void {
    const profile = this.profileStore.getActiveProfile();
    const config = this.profileStore.getConfig();

    const payload: GridSyncPayload = {
      activeProfileId: config.activeProfileId,
      activePageIndex: config.activePageIndex,
      gridConfig: profile ? profile.gridConfig : { rows: 3, cols: 4 },
      buttons: this.profileStore.getActivePageButtons()
    };

    if (ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          event: EventTypes.GRID_SYNC,
          payload
        })
      );
    }
  }

  public broadcastGridSync(): void {
    const profile = this.profileStore.getActiveProfile();
    const config = this.profileStore.getConfig();

    const payload: GridSyncPayload = {
      activeProfileId: config.activeProfileId,
      activePageIndex: config.activePageIndex,
      gridConfig: profile ? profile.gridConfig : { rows: 3, cols: 4 },
      buttons: this.profileStore.getActivePageButtons()
    };

    this.broadcast({
      event: EventTypes.GRID_SYNC,
      payload
    });
  }

  public broadcast(message: WebSocketMessage): void {
    if (!this.wss) return;
    const json = JSON.stringify(message);
    this.wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(json);
      }
    });
  }

  public getConnectedClientsCount(): number {
    return this.connectedClientsCount;
  }
}
