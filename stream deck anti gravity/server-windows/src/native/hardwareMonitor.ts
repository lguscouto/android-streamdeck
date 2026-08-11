import si from 'systeminformation';

export interface HardwareMetrics {
  cpuUsage: number; // Porcentagem (0 - 100%)
  cpuTemp: number; // Temperatura em Celsius
  ramUsage: number; // Porcentagem (0 - 100%)
  ramUsedGb: string;
  ramTotalGb: string;
  gpuUsage: number; // Porcentagem (0 - 100%)
}

export class HardwareMonitor {
  private timer: NodeJS.Timeout | null = null;
  private onMetricsCallback?: (metrics: HardwareMetrics) => void;

  public registerMetricsHandler(callback: (metrics: HardwareMetrics) => void): void {
    this.onMetricsCallback = callback;
  }

  public start(intervalMs: number = 1000): void {
    this.stop();
    this.timer = setInterval(async () => {
      try {
        const metrics = await this.getMetrics();
        if (this.onMetricsCallback) {
          this.onMetricsCallback(metrics);
        }
      } catch (err) {
        console.error('[HardwareMonitor] Erro ao coletar métricas de hardware:', err);
      }
    }, intervalMs);
  }

  public stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  public async getMetrics(): Promise<HardwareMetrics> {
    const currentLoad = await si.currentLoad();
    const mem = await si.mem();
    const temp = await si.cpuTemperature();
    const graphics = await si.graphics();

    const cpuUsage = Math.round(currentLoad.currentLoad || 0);
    const cpuTemp = Math.round(temp.main || 45);

    const ramUsage = Math.round((mem.active / mem.total) * 100);
    const ramUsedGb = (mem.active / (1024 * 1024 * 1024)).toFixed(1);
    const ramTotalGb = (mem.total / (1024 * 1024 * 1024)).toFixed(1);

    let gpuUsage = 0;
    if (graphics.controllers && graphics.controllers.length > 0) {
      gpuUsage = Math.round(graphics.controllers[0].utilizationGpu || 0);
    }

    return {
      cpuUsage,
      cpuTemp,
      ramUsage,
      ramUsedGb,
      ramTotalGb,
      gpuUsage
    };
  }
}
