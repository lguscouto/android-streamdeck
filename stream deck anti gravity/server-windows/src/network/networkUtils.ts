import os from 'os';
import QRCode from 'qrcode';

export class NetworkUtils {
  /**
   * Obtém o primeiro IP IPv4 não-loopback da rede local (ex: 192.168.x.x).
   */
  public static getLocalIpAddress(): string {
    const interfaces = os.networkInterfaces();
    for (const name of Object.keys(interfaces)) {
      const iface = interfaces[name];
      if (!iface) continue;
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
  public static async generatePairingQrCode(wsPort: number = 5001, httpPort: number = 5000): Promise<string> {
    const ip = this.getLocalIpAddress();
    const payload = JSON.stringify({
      ip,
      wsPort,
      httpPort,
      name: 'AntiGravity Host PC',
      timestamp: Date.now()
    });

    return QRCode.toDataURL(payload, { margin: 2, scale: 6 });
  }
}
