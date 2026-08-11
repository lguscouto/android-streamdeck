import { exec } from 'child_process';

export class KeyboardController {
  /**
   * Dispara um atalho de mídia no Windows via Virtual Key Code.
   * VK_VOLUME_MUTE = 0xAD (173)
   * VK_VOLUME_DOWN = 0xAE (174)
   * VK_VOLUME_UP   = 0xAF (175)
   * VK_MEDIA_NEXT  = 0xB0 (176)
   * VK_MEDIA_PREV  = 0xB1 (177)
   * VK_PLAY_PAUSE  = 0xB3 (179)
   */
  public static sendMediaKey(keyCode: number): Promise<boolean> {
    return new Promise((resolve) => {
      const psCommand = `powershell -Command "$member = '[DllImport(\\"user32.dll\\")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, uint dwExtraInfo);'; $type = Add-Type -MemberDefinition $member -Name \\"WinKey\\" -Namespace \\"Win32\\" -PassThru; $type::keybd_event(${keyCode}, 0, 0, 0); $type::keybd_event(${keyCode}, 0, 2, 0);"`;

      exec(psCommand, (err) => {
        if (err) console.error('[KeyboardController] Erro ao enviar tecla de mídia:', err);
        resolve(!err);
      });
    });
  }

  public static playPause(): Promise<boolean> {
    return this.sendMediaKey(179);
  }

  public static volumeUp(): Promise<boolean> {
    return this.sendMediaKey(175);
  }

  public static volumeDown(): Promise<boolean> {
    return this.sendMediaKey(174);
  }

  public static mute(): Promise<boolean> {
    return this.sendMediaKey(173);
  }

  public static nextTrack(): Promise<boolean> {
    return this.sendMediaKey(176);
  }

  public static prevTrack(): Promise<boolean> {
    return this.sendMediaKey(177);
  }

  /**
   * Envia uma combinação de teclas (ex: "^c" para Ctrl+C, "%{F4}" para Alt+F4, "^+{M}" para Ctrl+Shift+M).
   */
  public static sendHotkey(sendKeysPattern: string): Promise<boolean> {
    return new Promise((resolve) => {
      const psCommand = `powershell -Command "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys('${sendKeysPattern}')"`;

      exec(psCommand, (err) => {
        if (err) console.error('[KeyboardController] Erro ao enviar hotkey:', err);
        resolve(!err);
      });
    });
  }
}
