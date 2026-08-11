import { exec } from 'child_process';
import { KeyboardController } from './keyboard';

export class AudioController {
  /**
   * Alterna o estado de Mute de Som.
   */
  public static async toggleMute(): Promise<boolean> {
    return KeyboardController.mute();
  }

  /**
   * Aumenta o volume master.
   */
  public static async volumeUp(): Promise<boolean> {
    return KeyboardController.volumeUp();
  }

  /**
   * Diminui o volume master.
   */
  public static async volumeDown(): Promise<boolean> {
    return KeyboardController.volumeDown();
  }
}
