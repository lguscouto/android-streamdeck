"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.KeyboardController = void 0;
const child_process_1 = require("child_process");
class KeyboardController {
    /**
     * Dispara um atalho de mídia no Windows via Virtual Key Code.
     * VK_VOLUME_MUTE = 0xAD (173)
     * VK_VOLUME_DOWN = 0xAE (174)
     * VK_VOLUME_UP   = 0xAF (175)
     * VK_MEDIA_NEXT  = 0xB0 (176)
     * VK_MEDIA_PREV  = 0xB1 (177)
     * VK_PLAY_PAUSE  = 0xB3 (179)
     */
    static sendMediaKey(keyCode) {
        return new Promise((resolve) => {
            const psCommand = `powershell -Command "$member = '[DllImport(\\"user32.dll\\")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, uint dwExtraInfo);'; $type = Add-Type -MemberDefinition $member -Name \\"WinKey\\" -Namespace \\"Win32\\" -PassThru; $type::keybd_event(${keyCode}, 0, 0, 0); $type::keybd_event(${keyCode}, 0, 2, 0);"`;
            (0, child_process_1.exec)(psCommand, (err) => {
                if (err)
                    console.error('[KeyboardController] Erro ao enviar tecla de mídia:', err);
                resolve(!err);
            });
        });
    }
    static playPause() {
        return this.sendMediaKey(179);
    }
    static volumeUp() {
        return this.sendMediaKey(175);
    }
    static volumeDown() {
        return this.sendMediaKey(174);
    }
    static mute() {
        return this.sendMediaKey(173);
    }
    static nextTrack() {
        return this.sendMediaKey(176);
    }
    static prevTrack() {
        return this.sendMediaKey(177);
    }
    /**
     * Envia uma combinação de teclas (ex: "^c" para Ctrl+C, "%{F4}" para Alt+F4, "^+{M}" para Ctrl+Shift+M).
     */
    static sendHotkey(sendKeysPattern) {
        return new Promise((resolve) => {
            const psCommand = `powershell -Command "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys('${sendKeysPattern}')"`;
            (0, child_process_1.exec)(psCommand, (err) => {
                if (err)
                    console.error('[KeyboardController] Erro ao enviar hotkey:', err);
                resolve(!err);
            });
        });
    }
}
exports.KeyboardController = KeyboardController;
