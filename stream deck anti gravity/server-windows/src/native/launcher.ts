import { exec } from 'child_process';

export class AppLauncher {
  /**
   * Abre um aplicativo, arquivo ou comando no Windows.
   */
  public static launchApp(commandOrPath: string): Promise<boolean> {
    return new Promise((resolve) => {
      // Se for uma URL
      if (commandOrPath.startsWith('http://') || commandOrPath.startsWith('https://')) {
        exec(`start "" "${commandOrPath}"`, (err) => {
          if (err) console.error('[AppLauncher] Erro ao abrir URL:', err);
          resolve(!err);
        });
        return;
      }

      // Executável ou caminho de arquivo
      exec(`"${commandOrPath}"`, (err) => {
        if (err) {
          // Tentar via start para lidar com arquivos associados
          exec(`start "" "${commandOrPath}"`, (err2) => {
            if (err2) console.error('[AppLauncher] Erro ao abrir aplicação:', err2);
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
  public static openUrl(url: string): Promise<boolean> {
    return this.launchApp(url);
  }
}
