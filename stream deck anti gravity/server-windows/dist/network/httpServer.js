"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.HttpServer = void 0;
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const networkUtils_1 = require("./networkUtils");
const iconManager_1 = require("../config/iconManager");
class HttpServer {
    app;
    port;
    profileStore;
    iconManager;
    onProfileUpdatedCallback;
    connectedClientsGetter;
    startTime = new Date();
    constructor(port = 5000, profileStore) {
        this.app = (0, express_1.default)();
        this.port = port;
        this.profileStore = profileStore;
        this.iconManager = new iconManager_1.IconManager();
        this.configureMiddleware();
        this.configureRoutes();
    }
    registerProfileUpdatedHandler(callback) {
        this.onProfileUpdatedCallback = callback;
    }
    registerConnectedClientsGetter(getter) {
        this.connectedClientsGetter = getter;
    }
    configureMiddleware() {
        this.app.use((0, cors_1.default)());
        this.app.use(express_1.default.json({ limit: '10mb' }));
        const publicDir = path_1.default.join(__dirname, '../../public');
        if (fs_1.default.existsSync(publicDir)) {
            this.app.use('/', express_1.default.static(publicDir));
        }
        const sharedIconsDir = path_1.default.join(__dirname, '../../../shared/default-icons');
        const customIconsDir = path_1.default.join(__dirname, '../../data/custom-icons');
        if (fs_1.default.existsSync(sharedIconsDir)) {
            this.app.use('/api/icons', express_1.default.static(sharedIconsDir));
        }
        if (fs_1.default.existsSync(customIconsDir)) {
            this.app.use('/api/icons/custom', express_1.default.static(customIconsDir));
        }
    }
    configureRoutes() {
        this.app.get('/api/info', (_req, res) => {
            res.json({
                serverName: 'AntiGravity Stream Deck V2',
                ip: networkUtils_1.NetworkUtils.getLocalIpAddress(),
                version: '2.0.0',
                webSocketPort: 5001,
                authenticated: true
            });
        });
        this.app.get('/api/health', (_req, res) => {
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
        this.app.get('/api/pairing', async (_req, res) => {
            try {
                const localIp = networkUtils_1.NetworkUtils.getLocalIpAddress();
                const qrCodeDataUrl = await networkUtils_1.NetworkUtils.generatePairingQrCode(5001, this.port);
                res.json({
                    serverName: 'AntiGravity Host PC',
                    ip: localIp,
                    wsPort: 5001,
                    httpPort: this.port,
                    qrCode: qrCodeDataUrl
                });
            }
            catch (err) {
                res.status(500).json({ error: err.message });
            }
        });
        this.app.get('/api/icons-catalog', (_req, res) => {
            res.json(this.iconManager.getAvailableIcons());
        });
        this.app.get('/api/profiles', (_req, res) => {
            res.json(this.profileStore.getConfig());
        });
        this.app.post('/api/profiles/select', (req, res) => {
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
        this.app.post('/api/profiles/create', (req, res) => {
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
        this.app.post('/api/profiles/update', (req, res) => {
            try {
                const { profileId, pageIndex, buttons } = req.body;
                if (!profileId || buttons === undefined) {
                    res.status(400).json({ error: 'profileId e buttons são obrigatórios.' });
                    return;
                }
                buttons.forEach((b) => {
                    this.profileStore.updateButton(profileId, pageIndex || 0, b);
                });
                if (this.onProfileUpdatedCallback) {
                    this.onProfileUpdatedCallback();
                }
                res.json({ success: true });
            }
            catch (err) {
                res.status(500).json({ error: err.message });
            }
        });
        this.app.post('/api/icons/upload', (req, res) => {
            try {
                const { filename, base64Data } = req.body;
                if (!filename || !base64Data) {
                    res.status(400).json({ error: 'filename e base64Data são obrigatórios.' });
                    return;
                }
                const customIconsDir = path_1.default.join(__dirname, '../../data/custom-icons');
                if (!fs_1.default.existsSync(customIconsDir)) {
                    fs_1.default.mkdirSync(customIconsDir, { recursive: true });
                }
                const buffer = Buffer.from(base64Data, 'base64');
                const targetPath = path_1.default.join(customIconsDir, filename);
                fs_1.default.writeFileSync(targetPath, buffer);
                res.json({
                    success: true,
                    iconUrl: `/api/icons/custom/${filename}`
                });
            }
            catch (err) {
                res.status(500).json({ error: err.message });
            }
        });
    }
    start() {
        return new Promise((resolve) => {
            this.app.listen(this.port, () => {
                const ip = networkUtils_1.NetworkUtils.getLocalIpAddress();
                console.log(`[HttpServer] Editor Desktop UI em http://localhost:${this.port}`);
                console.log(`[HttpServer] IP da Rede Local: http://${ip}:${this.port}`);
                resolve();
            });
        });
    }
}
exports.HttpServer = HttpServer;
