import { ProfileStore } from '../config/profileStore';
import { AppLauncher } from '../native/launcher';
import { KeyboardController } from '../native/keyboard';
import { AudioController } from '../native/audio';
import { ObsController } from '../native/obsController';
import { DiscordController } from '../native/discordController';
import { PressButtonPayload, ButtonModel } from '../protocol';

export interface SubAction {
  actionType: string;
  actionPayload?: Record<string, any>;
  delayMs?: number;
}

export class Engine {
  private profileStore: ProfileStore;
  private obs: ObsController;
  private onStateChangeCallback?: (buttonId: string, newState: string) => void;
  private onGridSyncCallback?: () => void;

  constructor(profileStore: ProfileStore) {
    this.profileStore = profileStore;
    this.obs = new ObsController();
  }

  public registerStateChangeHandler(fn: (buttonId: string, newState: string) => void): void {
    this.onStateChangeCallback = fn;
  }

  public registerGridSyncHandler(fn: () => void): void {
    this.onGridSyncCallback = fn;
  }

  public async handlePressButton(payload: PressButtonPayload): Promise<void> {
    const { profileId, pageIndex, buttonId, actionType } = payload;
    console.log(`[Engine] Botão pressionado: id=${buttonId}, actionType=${actionType}`);

    const config = this.profileStore.getConfig();
    const profile = config.profiles.find((p) => p.id === profileId);
    if (!profile) return;

    const page = profile.pages[pageIndex] || profile.pages[0];
    const button = page?.buttons.find((b: ButtonModel) => b.id === buttonId);

    if (!button) return;

    const currentState = button.state || 'OFF';
    const nextState = currentState === 'OFF' ? 'ON' : 'OFF';

    if (button.actionType === 'MULTI_ACTION') {
      await this.executeMultiAction(button.actionPayload?.actions || []);
    } else {
      await this.executeSingleAction(button.actionType || 'NONE', button.actionPayload);
    }

    button.state = nextState;
    this.profileStore.save();

    if (this.onStateChangeCallback) {
      this.onStateChangeCallback(buttonId, nextState);
    }
  }

  private async executeMultiAction(actions: SubAction[]): Promise<void> {
    console.log(`[Engine] Executando Macro Multi-Action (${actions.length} passos)...`);
    for (const sub of actions) {
      if (sub.delayMs && sub.delayMs > 0) {
        await new Promise((r) => setTimeout(r, sub.delayMs));
      }
      await this.executeSingleAction(sub.actionType, sub.actionPayload);
    }
  }

  private async executeSingleAction(actionType: string, payload?: Record<string, any>): Promise<void> {
    switch (actionType) {
      case 'TOGGLE_MUTE':
        AudioController.toggleMute();
        break;

      case 'VOLUME_UP':
        AudioController.volumeUp();
        break;

      case 'VOLUME_DOWN':
        AudioController.volumeDown();
        break;

      case 'MEDIA_PLAY_PAUSE':
        KeyboardController.playPause();
        break;

      case 'HOTKEY':
        if (payload?.keys) {
          KeyboardController.sendHotkey(payload.keys);
        }
        break;

      case 'OPEN_APP':
        if (payload?.path) {
          AppLauncher.launchApp(payload.path);
        }
        break;

      case 'OPEN_URL':
        if (payload?.url) {
          AppLauncher.openUrl(payload.url);
        }
        break;

      case 'OBS_SCENE':
        if (payload?.sceneName) {
          await this.obs.setScene(payload.sceneName);
        }
        break;

      case 'OBS_TOGGLE_STREAM':
        await this.obs.toggleStream();
        break;

      case 'OBS_TOGGLE_RECORD':
        await this.obs.toggleRecord();
        break;

      case 'DISCORD_TOGGLE_MUTE':
        DiscordController.toggleMute();
        break;

      case 'DISCORD_TOGGLE_DEAFEN':
        DiscordController.toggleDeafen();
        break;

      default:
        console.log(`[Engine] Nenhuma ação nativa executada para ${actionType}`);
        break;
    }
  }

  public handleSwitchPage(payload: { profileId: string; pageIndex: number }): void {
    this.profileStore.setActivePage(payload.pageIndex);
    if (this.onGridSyncCallback) {
      this.onGridSyncCallback();
    }
  }
}
