"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ObsController = void 0;
const obs_websocket_js_1 = __importDefault(require("obs-websocket-js"));
class ObsController {
    obs;
    connected = false;
    constructor() {
        this.obs = new obs_websocket_js_1.default();
    }
    async connect(url = 'ws://127.0.0.1:4455', password) {
        try {
            await this.obs.connect(url, password);
            this.connected = true;
            console.log('[ObsController] Conectado com sucesso ao OBS Studio!');
            return true;
        }
        catch (err) {
            console.warn('[ObsController] Não foi possível conectar ao OBS Studio (verifique se o OBS WebSocket está ativo):', err.message);
            this.connected = false;
            return false;
        }
    }
    async setScene(sceneName) {
        if (!this.connected) {
            const ok = await this.connect();
            if (!ok)
                return false;
        }
        try {
            await this.obs.call('SetCurrentProgramScene', { sceneName });
            console.log(`[ObsController] Cena alterada para: ${sceneName}`);
            return true;
        }
        catch (err) {
            console.error('[ObsController] Erro ao mudar cena no OBS:', err.message);
            return false;
        }
    }
    async toggleStream() {
        if (!this.connected) {
            const ok = await this.connect();
            if (!ok)
                return false;
        }
        try {
            const status = await this.obs.call('ToggleStream');
            console.log('[ObsController] Stream alternado:', status.outputActive);
            return status.outputActive;
        }
        catch (err) {
            console.error('[ObsController] Erro ao alternar stream no OBS:', err.message);
            return false;
        }
    }
    async toggleRecord() {
        if (!this.connected) {
            const ok = await this.connect();
            if (!ok)
                return false;
        }
        try {
            const status = await this.obs.call('ToggleRecord');
            console.log('[ObsController] Gravação alternada:', status.outputActive);
            return status.outputActive;
        }
        catch (err) {
            console.error('[ObsController] Erro ao alternar gravação no OBS:', err.message);
            return false;
        }
    }
    isConnected() {
        return this.connected;
    }
}
exports.ObsController = ObsController;
