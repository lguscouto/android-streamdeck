import OBSWebSocket from 'obs-websocket-js';

export class ObsController {
  private obs: OBSWebSocket;
  private connected: boolean = false;

  constructor() {
    this.obs = new OBSWebSocket();
  }

  public async connect(url: string = 'ws://127.0.0.1:4455', password?: string): Promise<boolean> {
    try {
      await this.obs.connect(url, password);
      this.connected = true;
      console.log('[ObsController] Conectado com sucesso ao OBS Studio!');
      return true;
    } catch (err: any) {
      console.warn('[ObsController] Não foi possível conectar ao OBS Studio (verifique se o OBS WebSocket está ativo):', err.message);
      this.connected = false;
      return false;
    }
  }

  public async setScene(sceneName: string): Promise<boolean> {
    if (!this.connected) {
      const ok = await this.connect();
      if (!ok) return false;
    }

    try {
      await this.obs.call('SetCurrentProgramScene', { sceneName });
      console.log(`[ObsController] Cena alterada para: ${sceneName}`);
      return true;
    } catch (err: any) {
      console.error('[ObsController] Erro ao mudar cena no OBS:', err.message);
      return false;
    }
  }

  public async toggleStream(): Promise<boolean> {
    if (!this.connected) {
      const ok = await this.connect();
      if (!ok) return false;
    }

    try {
      const status = await this.obs.call('ToggleStream');
      console.log('[ObsController] Stream alternado:', status.outputActive);
      return status.outputActive;
    } catch (err: any) {
      console.error('[ObsController] Erro ao alternar stream no OBS:', err.message);
      return false;
    }
  }

  public async toggleRecord(): Promise<boolean> {
    if (!this.connected) {
      const ok = await this.connect();
      if (!ok) return false;
    }

    try {
      const status = await this.obs.call('ToggleRecord');
      console.log('[ObsController] Gravação alternada:', status.outputActive);
      return status.outputActive;
    } catch (err: any) {
      console.error('[ObsController] Erro ao alternar gravação no OBS:', err.message);
      return false;
    }
  }

  public isConnected(): boolean {
    return this.connected;
  }
}
