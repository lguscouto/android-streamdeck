import fs from 'fs';
import path from 'path';

export interface IconItem {
  id: string;
  name: string;
  url: string;
  type: 'DEFAULT' | 'CUSTOM';
}

export class IconManager {
  private defaultIconsDir: string;
  private customIconsDir: string;

  constructor() {
    this.defaultIconsDir = path.join(__dirname, '../../../shared/default-icons');
    this.customIconsDir = path.join(__dirname, '../../data/custom-icons');

    if (!fs.existsSync(this.customIconsDir)) {
      fs.mkdirSync(this.customIconsDir, { recursive: true });
    }
  }

  public getAvailableIcons(): IconItem[] {
    const list: IconItem[] = [];

    // Ícones Padrão (SVG, PNG, GIF, WEBP, JPG)
    if (fs.existsSync(this.defaultIconsDir)) {
      const files = fs.readdirSync(this.defaultIconsDir);
      files.forEach((file) => {
        if (/\.(svg|png|jpg|jpeg|gif|webp)$/i.test(file)) {
          list.push({
            id: file,
            name: path.parse(file).name,
            url: `/api/icons/${file}`,
            type: 'DEFAULT'
          });
        }
      });
    }

    // Ícones Customizados
    if (fs.existsSync(this.customIconsDir)) {
      const files = fs.readdirSync(this.customIconsDir);
      files.forEach((file) => {
        if (/\.(svg|png|jpg|jpeg|gif|webp)$/i.test(file)) {
          list.push({
            id: `custom_${file}`,
            name: path.parse(file).name,
            url: `/api/icons/custom/${file}`,
            type: 'CUSTOM'
          });
        }
      });
    }

    return list;
  }
}
