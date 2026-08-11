"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DiscordController = void 0;
const keyboard_1 = require("./keyboard");
class DiscordController {
    /**
     * Envia o atalho padrão de Mutar Microfone no Discord (Ctrl + Shift + M)
     */
    static toggleMute() {
        console.log('[DiscordController] Alternando Mute no Discord (Ctrl+Shift+M)...');
        keyboard_1.KeyboardController.sendHotkey('^+m');
    }
    /**
     * Envia o atalho padrão de Mutar Áudio/Deafen no Discord (Ctrl + Shift + D)
     */
    static toggleDeafen() {
        console.log('[DiscordController] Alternando Deafen no Discord (Ctrl+Shift+D)...');
        keyboard_1.KeyboardController.sendHotkey('^+d');
    }
}
exports.DiscordController = DiscordController;
