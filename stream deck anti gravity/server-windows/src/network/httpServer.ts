import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { ProfileStore } from '../config/profileStore';
import { NetworkUtils } from './networkUtils';
import { IconManager } from '../config/iconManager';

export class HttpServer {
  private app: express.Application;
  private port: number;
  private profileStore: ProfileStore;
  private iconManager: IconManager;
  private onProfileUpdatedCallback?: () => void;
  private connectedClientsGetter?: () => number;
  private startTime: Date = new Date();

  constructor(port: number = 5000, profileStore: ProfileStore) {
    this.app = express();
    this.port = port;
    this.profileStore = profileStore;
    this.iconManager = new IconManager();

    this.configureMiddleware();
    this.configureRoutes();
  }

  public registerProfileUpdatedHandler(callback: () => void): void {
    this.onProfileUpdatedCallback = callback;
  }

  public registerConnectedClientsGetter(getter: () => number): void {
    this.connectedClientsGetter = getter;
  }

  private configureMiddleware(): void {
    this.app.use(cors());
    this.app.use(express.json({ limit: '10mb' }));

    const publicDir = path.join(__dirname, '../../public');
    if (fs.existsSync(publicDir)) {
      this.app.use('/', express.static(publicDir));
    }

    const sharedIconsDir = path.join(__dirname, '../../../shared/default-icons');
    const customIconsDir = path.join(__dirname, '../../data/custom-icons');

    if (fs.existsSync(sharedIconsDir)) {
      this.app.use('/api/icons', express.static(sharedIconsDir));
    }
    if (fs.existsSync(customIconsDir)) {
      this.app.use('/api/icons/custom', express.static(customIconsDir));
    }
  }

  private configureRoutes(): void {
    this.app.get('/api/info', (_req: Request, res: Response) => {
      res.json({
        serverName: 'AntiGravity Stream Deck V2',
        ip: NetworkUtils.getLocalIpAddress(),
        version: '2.0.0',
        webSocketPort: 5001,
        authenticated: true
      });
    });

    this.app.get('/api/health', (_req: Request, res: Response) => {
      const uptimeMs = Date.now() - this.startTime.getTime();
      const uptimeSec = Math.floor(uptimeMs / 1000);
      const mem = process.memoryUsage();
      res.json({
        status: 'ok',
        version: '2.0.0',
        uptime: {
          seconds: uptimeSec,
          human: `${Math.floor(uptimeSec / 3600)}h ${Math.floor((uptimeSec % 3600) / 60)}m ${uptimeSec % 60}s`
        },
        memory: {
          heapUsedMB: Math.round(mem.heapUsed / 1024 / 1024),
          heapTotalMB: Math.round(mem.heapTotal / 1024 / 1024),
          rssMB: Math.round(mem.rss / 1024 / 1024)
        },
        connectedClients: this.connectedClientsGetter ? this.connectedClientsGetter() : 0,
        node: process.version,
        platform: process.platform,
        timestamp: new Date().toISOString()
      });
    });

    this.app.get('/api/pairing', async (_req: Request, res: Response) => {
      try {
        const localIp = NetworkUtils.getLocalIpAddress();
        const qrCodeDataUrl = await NetworkUtils.generatePairingQrCode(5001, this.port);

        res.json({
          serverName: 'AntiGravity Host PC',
          ip: localIp,
          wsPort: 5001,
          httpPort: this.port,
          qrCode: qrCodeDataUrl
        });
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    this.app.get('/api/icons-catalog', (_req: Request, res: Response) => {
      res.json(this.iconManager.getAvailableIcons());
    });

    this.app.get('/api/profiles', (_req: Request, res: Response) => {
      res.json(this.profileStore.getConfig());
    });

    this.app.post('/api/profiles/select', (req: Request, res: Response) => {
      const { profileId, pageIndex } = req.body;
      if (profileId) {
        this.profileStore.setActiveProfile(profileId);
      }
      if (pageIndex !== undefined) {
        this.profileStore.setActivePage(pageIndex);
      }

      if (this.onProfileUpdatedCallback) {
        this.onProfileUpdatedCallback();
      }

      res.json({ success: true, config: this.profileStore.getConfig() });
    });

    this.app.post('/api/profiles/create', (req: Request, res: Response) => {
      const { id, name } = req.body;
      if (!id || !name) {
        res.status(400).json({ error: 'id e name são obrigatórios.' });
        return;
      }

      const newProfile = this.profileStore.createProfile(id, name);
      if (this.onProfileUpdatedCallback) {
        this.onProfileUpdatedCallback();
      }

      res.json({ success: true, profile: newProfile });
    });

    this.app.post('/api/profiles/update', (req: Request, res: Response) => {
      try {
        const { profileId, pageIndex, buttons } = req.body;
        if (!profileId || buttons === undefined) {
          res.status(400).json({ error: 'profileId e buttons são obrigatórios.' });
          return;
        }

        buttons.forEach((b: any) => {
          this.profileStore.updateButton(profileId, pageIndex || 0, b);
        });

        if (this.onProfileUpdatedCallback) {
          this.onProfileUpdatedCallback();
        }

        res.json({ success: true });
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });

    this.app.post('/api/icons/upload', (req: Request, res: Response) => {
      try {
        const { filename, base64Data } = req.body;
        if (!filename || !base64Data) {
          res.status(400).json({ error: 'filename e base64Data são obrigatórios.' });
          return;
        }

        const customIconsDir = path.join(__dirname, '../../data/custom-icons');
        if (!fs.existsSync(customIconsDir)) {
          fs.mkdirSync(customIconsDir, { recursive: true });
        }

        const buffer = Buffer.from(base64Data, 'base64');
        const targetPath = path.join(customIconsDir, filename);
        fs.writeFileSync(targetPath, buffer);

        res.json({
          success: true,
          iconUrl: `/api/icons/custom/${filename}`
        });
      } catch (err: any) {
        res.status(500).json({ error: err.message });
      }
    });
  }

  public start(): Promise<void> {
    return new Promise((resolve) => {
      this.app.listen(this.port, () => {
        const ip = NetworkUtils.getLocalIpAddress();
        console.log(`[HttpServer] Editor Desktop UI em http://localhost:${this.port}`);
        console.log(`[HttpServer] IP da Rede Local: http://${ip}:${this.port}`);
        resolve();
      });
    });
  }
}
