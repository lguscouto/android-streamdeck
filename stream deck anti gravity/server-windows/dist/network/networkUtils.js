"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.NetworkUtils = void 0;
const os_1 = __importDefault(require("os"));
const qrcode_1 = __importDefault(require("qrcode"));
class NetworkUtils {
    /**
     * Obtém o primeiro IP IPv4 não-loopback da rede local (ex: 192.168.x.x).
     */
    static getLocalIpAddress() {
        const interfaces = os_1.default.networkInterfaces();
        for (const name of Object.keys(interfaces)) {
            const iface = interfaces[name];
            if (!iface)
                continue;
            for (const alias of iface) {
                if (alias.family === 'IPv4' && !alias.internal) {
                    return alias.address;
                }
            }
        }
        return '127.0.0.1';
    }
    /**
     * Gera uma imagem Data URL Base64 de um QR Code contendo as informações de pareamento.
     */
    static async generatePairingQrCode(wsPort = 5001, httpPort = 5000) {
        const ip = this.getLocalIpAddress();
        const payload = JSON.stringify({
            ip,
            wsPort,
            httpPort,
            name: 'AntiGravity Host PC',
            timestamp: Date.now()
        });
        return qrcode_1.default.toDataURL(payload, { margin: 2, scale: 6 });
    }
}
exports.NetworkUtils = NetworkUtils;
