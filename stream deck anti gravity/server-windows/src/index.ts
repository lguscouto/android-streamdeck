import { ProfileStore } from './config/profileStore';
import { Engine } from './core/engine';
import { HttpServer } from './network/httpServer';
import { WsServer } from './network/wsServer';
import { HardwareMonitor } from './native/hardwareMonitor';
import { SpotifyController } from './native/spotifyController';
import { EventTypes } from './protocol';

async function bootstrap() {
  console.log('----------------------------------------------------');
  console.log('🚀 Iniciando AntiGravity Stream Deck Server V2 (Windows)');
  console.log('----------------------------------------------------');

  const profileStore = new ProfileStore();
  const engine = new Engine(profileStore);

  const httpServer = new HttpServer(5000, profileStore);
  const wsServer = new WsServer(5001, profileStore, engine);

  httpServer.registerProfileUpdatedHandler(() => {
    console.log('[Bootstrap] Perfil atualizado via Web UI! Sincronizando com Android...');
    wsServer.broadcastGridSync();
  });

  httpServer.registerConnectedClientsGetter(() => wsServer.getConnectedClientsCount());

  const hardwareMonitor = new HardwareMonitor();
  hardwareMonitor.registerMetricsHandler((metrics) => {
    wsServer.broadcast({
      event: EventTypes.HARDWARE_SYNC,
      payload: metrics
    });
  });
  hardwareMonitor.start(1000);

  const spotifyController = new SpotifyController();
  setInterval(async () => {
    try {
      const track = await spotifyController.getCurrentTrack();
      wsServer.broadcast({
        event: EventTypes.SPOTIFY_SYNC,
        payload: track
      });
    } catch (_e) {}
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
