"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.IconManager = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
class IconManager {
    defaultIconsDir;
    customIconsDir;
    constructor() {
        this.defaultIconsDir = path_1.default.join(__dirname, '../../../shared/default-icons');
        this.customIconsDir = path_1.default.join(__dirname, '../../data/custom-icons');
        if (!fs_1.default.existsSync(this.customIconsDir)) {
            fs_1.default.mkdirSync(this.customIconsDir, { recursive: true });
        }
    }
    getAvailableIcons() {
        const list = [];
        // Ícones Padrão (SVG, PNG, GIF, WEBP, JPG)
        if (fs_1.default.existsSync(this.defaultIconsDir)) {
            const files = fs_1.default.readdirSync(this.defaultIconsDir);
            files.forEach((file) => {
                if (/\.(svg|png|jpg|jpeg|gif|webp)$/i.test(file)) {
                    list.push({
                        id: file,
                        name: path_1.default.parse(file).name,
                        url: `/api/icons/${file}`,
                        type: 'DEFAULT'
                    });
                }
            });
        }
        // Ícones Customizados
        if (fs_1.default.existsSync(this.customIconsDir)) {
            const files = fs_1.default.readdirSync(this.customIconsDir);
            files.forEach((file) => {
                if (/\.(svg|png|jpg|jpeg|gif|webp)$/i.test(file)) {
                    list.push({
                        id: `custom_${file}`,
                        name: path_1.default.parse(file).name,
                        url: `/api/icons/custom/${file}`,
                        type: 'CUSTOM'
                    });
                }
            });
        }
        return list;
    }
}
exports.IconManager = IconManager;
