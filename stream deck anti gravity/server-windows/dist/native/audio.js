"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AudioController = void 0;
const keyboard_1 = require("./keyboard");
class AudioController {
    /**
     * Alterna o estado de Mute de Som.
     */
    static async toggleMute() {
        return keyboard_1.KeyboardController.mute();
    }
    /**
     * Aumenta o volume master.
     */
    static async volumeUp() {
        return keyboard_1.KeyboardController.volumeUp();
    }
    /**
     * Diminui o volume master.
     */
    static async volumeDown() {
        return keyboard_1.KeyboardController.volumeDown();
    }
}
exports.AudioController = AudioController;
