import { exec } from 'child_process';

export interface SpotifyTrackInfo {
  title: string;
  artist: string;
  isPlaying: boolean;
}

export class SpotifyController {
  public async getCurrentTrack(): Promise<SpotifyTrackInfo> {
    return new Promise((resolve) => {
      // Método 1: Tenta obter o título da janela do processo do Spotify no Windows
      const psCmd = `powershell -NoProfile -Command "(Get-Process spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 1).MainWindowTitle"`;

      exec(psCmd, (err, stdout) => {
        const rawTitle = stdout ? stdout.trim() : '';

        if (rawTitle && rawTitle.includes(' - ')) {
          const parts = rawTitle.split(' - ');
          const artist = parts[0].trim();
          const title = parts.slice(1).join(' - ').trim();

          return resolve({
            title,
            artist,
            isPlaying: true
          });
        } else if (rawTitle) {
          return resolve({
            title: rawTitle,
            artist: 'Spotify',
            isPlaying: true
          });
        }

        // Se o Spotify não estiver rodando ou estiver pausado sem faixa ativa
        resolve({
          title: 'Nenhuma música tocando',
          artist: 'Spotify',
          isPlaying: false
        });
      });
    });
  }
}
