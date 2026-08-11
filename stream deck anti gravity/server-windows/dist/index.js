"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const profileStore_1 = require("./config/profileStore");
const engine_1 = require("./core/engine");
const httpServer_1 = require("./network/httpServer");
const wsServer_1 = require("./network/wsServer");
const hardwareMonitor_1 = require("./native/hardwareMonitor");
const spotifyController_1 = require("./native/spotifyController");
const protocol_1 = require("./protocol");
async function bootstrap() {
    console.log('----------------------------------------------------');
    console.log('🚀 Iniciando AntiGravity Stream Deck Server V2 (Windows)');
    console.log('----------------------------------------------------');
    const profileStore = new profileStore_1.ProfileStore();
    const engine = new engine_1.Engine(profileStore);
    const httpServer = new httpServer_1.HttpServer(5000, profileStore);
    const wsServer = new wsServer_1.WsServer(5001, profileStore, engine);
    httpServer.registerProfileUpdatedHandler(() => {
        console.log('[Bootstrap] Perfil atualizado via Web UI! Sincronizando com Android...');
        wsServer.broadcastGridSync();
    });
    httpServer.registerConnectedClientsGetter(() => wsServer.getConnectedClientsCount());
    const hardwareMonitor = new hardwareMonitor_1.HardwareMonitor();
    hardwareMonitor.registerMetricsHandler((metrics) => {
        wsServer.broadcast({
            event: protocol_1.EventTypes.HARDWARE_SYNC,
            payload: metrics
        });
    });
    hardwareMonitor.start(1000);
    const spotifyController = new spotifyController_1.SpotifyController();
    setInterval(async () => {
        try {
            const track = await spotifyController.getCurrentTrack();
            wsServer.broadcast({
                event: protocol_1.EventTypes.SPOTIFY_SYNC,
                payload: track
            });
        }
        catch (_e) { }
    }, 2000);
    await httpServer.start();
    wsServer.start();
    console.log('✅ Servidor iniciado com sucesso!');
    console.log('💻 Dashboard Editor: http://localhost:5000');
    console.log('📡 HTTP API: http://localhost:5000/api/info');
    console.log('🔌 WebSocket: ws://localhost:5001');
}
bootstrap().catch((err) => {
    console.error('❌ Erro fatal na inicialização do servidor:', err);
});
