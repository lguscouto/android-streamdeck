import { KeyboardController } from './keyboard';

export class DiscordController {
  /**
   * Envia o atalho padrão de Mutar Microfone no Discord (Ctrl + Shift + M)
   */
  public static toggleMute(): void {
    console.log('[DiscordController] Alternando Mute no Discord (Ctrl+Shift+M)...');
    KeyboardController.sendHotkey('^+m');
  }

  /**
   * Envia o atalho padrão de Mutar Áudio/Deafen no Discord (Ctrl + Shift + D)
   */
  public static toggleDeafen(): void {
    console.log('[DiscordController] Alternando Deafen no Discord (Ctrl+Shift+D)...');
    KeyboardController.sendHotkey('^+d');
  }
}
