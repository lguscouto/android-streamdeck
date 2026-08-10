"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppLauncher = void 0;
const child_process_1 = require("child_process");
class AppLauncher {
    /**
     * Abre um aplicativo, arquivo ou comando no Windows.
     */
    static launchApp(commandOrPath) {
        return new Promise((resolve) => {
            // Se for uma URL
            if (commandOrPath.startsWith('http://') || commandOrPath.startsWith('https://')) {
                (0, child_process_1.exec)(`start "" "${commandOrPath}"`, (err) => {
                    if (err)
                        console.error('[AppLauncher] Erro ao abrir URL:', err);
                    resolve(!err);
                });
                return;
            }
            // Executável ou caminho de arquivo
            (0, child_process_1.exec)(`"${commandOrPath}"`, (err) => {
                if (err) {
                    // Tentar via start para lidar com arquivos associados
                    (0, child_process_1.exec)(`start "" "${commandOrPath}"`, (err2) => {
                        if (err2)
                            console.error('[AppLauncher] Erro ao abrir aplicação:', err2);
                        resolve(!err2);
                    });
                    return;
                }
                resolve(true);
            });
        });
    }
    /**
     * Abre uma URL no navegador padrão.
     */
    static openUrl(url) {
        return this.launchApp(url);
    }
}
exports.AppLauncher = AppLauncher;
