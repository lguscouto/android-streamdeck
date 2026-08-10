"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Engine = void 0;
const launcher_1 = require("../native/launcher");
const keyboard_1 = require("../native/keyboard");
const audio_1 = require("../native/audio");
const obsController_1 = require("../native/obsController");
const discordController_1 = require("../native/discordController");
class Engine {
    profileStore;
    obs;
    onStateChangeCallback;
    onGridSyncCallback;
    constructor(profileStore) {
        this.profileStore = profileStore;
        this.obs = new obsController_1.ObsController();
    }
    registerStateChangeHandler(fn) {
        this.onStateChangeCallback = fn;
    }
    registerGridSyncHandler(fn) {
        this.onGridSyncCallback = fn;
    }
    async handlePressButton(payload) {
        const { profileId, pageIndex, buttonId, actionType } = payload;
        console.log(`[Engine] Botão pressionado: id=${buttonId}, actionType=${actionType}`);
        const config = this.profileStore.getConfig();
        const profile = config.profiles.find((p) => p.id === profileId);
        if (!profile)
            return;
        const page = profile.pages[pageIndex] || profile.pages[0];
        const button = page?.buttons.find((b) => b.id === buttonId);
        if (!button)
            return;
        const currentState = button.state || 'OFF';
        const nextState = currentState === 'OFF' ? 'ON' : 'OFF';
        if (button.actionType === 'MULTI_ACTION') {
            await this.executeMultiAction(button.actionPayload?.actions || []);
        }
        else {
            await this.executeSingleAction(button.actionType || 'NONE', button.actionPayload);
        }
        button.state = nextState;
        this.profileStore.save();
        if (this.onStateChangeCallback) {
            this.onStateChangeCallback(buttonId, nextState);
        }
    }
    async executeMultiAction(actions) {
        console.log(`[Engine] Executando Macro Multi-Action (${actions.length} passos)...`);
        for (const sub of actions) {
            if (sub.delayMs && sub.delayMs > 0) {
                await new Promise((r) => setTimeout(r, sub.delayMs));
            }
            await this.executeSingleAction(sub.actionType, sub.actionPayload);
        }
    }
    async executeSingleAction(actionType, payload) {
        switch (actionType) {
            case 'TOGGLE_MUTE':
                audio_1.AudioController.toggleMute();
                break;
            case 'VOLUME_UP':
                audio_1.AudioController.volumeUp();
                break;
            case 'VOLUME_DOWN':
                audio_1.AudioController.volumeDown();
                break;
            case 'MEDIA_PLAY_PAUSE':
                keyboard_1.KeyboardController.playPause();
                break;
            case 'HOTKEY':
                if (payload?.keys) {
                    keyboard_1.KeyboardController.sendHotkey(payload.keys);
                }
                break;
            case 'OPEN_APP':
                if (payload?.path) {
                    launcher_1.AppLauncher.launchApp(payload.path);
                }
                break;
            case 'OPEN_URL':
                if (payload?.url) {
                    launcher_1.AppLauncher.openUrl(payload.url);
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
                discordController_1.DiscordController.toggleMute();
                break;
            case 'DISCORD_TOGGLE_DEAFEN':
                discordController_1.DiscordController.toggleDeafen();
                break;
            default:
                console.log(`[Engine] Nenhuma ação nativa executada para ${actionType}`);
                break;
        }
    }
    handleSwitchPage(payload) {
        this.profileStore.setActivePage(payload.pageIndex);
        if (this.onGridSyncCallback) {
            this.onGridSyncCallback();
        }
    }
}
exports.Engine = Engine;
