"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.HardwareMonitor = void 0;
const systeminformation_1 = __importDefault(require("systeminformation"));
class HardwareMonitor {
    timer = null;
    onMetricsCallback;
    registerMetricsHandler(callback) {
        this.onMetricsCallback = callback;
    }
    start(intervalMs = 1000) {
        this.stop();
        this.timer = setInterval(async () => {
            try {
                const metrics = await this.getMetrics();
                if (this.onMetricsCallback) {
                    this.onMetricsCallback(metrics);
                }
            }
            catch (err) {
                console.error('[HardwareMonitor] Erro ao coletar métricas de hardware:', err);
            }
        }, intervalMs);
    }
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }
    async getMetrics() {
        const currentLoad = await systeminformation_1.default.currentLoad();
        const mem = await systeminformation_1.default.mem();
        const temp = await systeminformation_1.default.cpuTemperature();
        const graphics = await systeminformation_1.default.graphics();
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
exports.HardwareMonitor = HardwareMonitor;
