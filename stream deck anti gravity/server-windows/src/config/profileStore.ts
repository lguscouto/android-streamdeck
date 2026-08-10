import fs from 'fs';
import path from 'path';
import { ButtonModel, GridConfig } from '../protocol';

export interface ProfilePage {
  pageIndex: number;
  buttons: ButtonModel[];
}

export interface Profile {
  id: string;
  name: string;
  gridConfig: GridConfig;
  pages: ProfilePage[];
}

export interface AppConfig {
  activeProfileId: string;
  activePageIndex: number;
  profiles: Profile[];
}

const DEFAULT_CONFIG_PATH = path.join(__dirname, '../../data/profiles.json');

const DEFAULT_CONFIG: AppConfig = {
  activeProfileId: 'default',
  activePageIndex: 0,
  profiles: [
    {
      id: 'default',
      name: 'Perfil Padrão',
      gridConfig: { rows: 3, cols: 4 },
      pages: [
        {
          pageIndex: 0,
          buttons: [
            {
              id: 'btn_mic_toggle',
              row: 0,
              col: 0,
              label: 'Mutar Mic',
              labelColor: '#FFFFFF',
              backgroundColor: '#E74C3C',
              iconUrl: '/api/icons/mic_off.svg',
              state: 'OFF',
              actionType: 'TOGGLE_MUTE',
              states: {
                OFF: { label: 'Mic OFF', iconUrl: '/api/icons/mic_off.svg', backgroundColor: '#E74C3C' },
                ON: { label: 'Mic ON', iconUrl: '/api/icons/mic_on.svg', backgroundColor: '#2ECC71' }
              }
            },
            {
              id: 'btn_media_play',
              row: 0,
              col: 1,
              label: 'Play / Pause',
              labelColor: '#FFFFFF',
              backgroundColor: '#3498DB',
              actionType: 'MEDIA_PLAY_PAUSE',
              iconUrl: '/api/icons/media_play.svg'
            },
            {
              id: 'btn_vol_up',
              row: 0,
              col: 2,
              label: 'Vol +',
              labelColor: '#FFFFFF',
              backgroundColor: '#2ECC71',
              actionType: 'VOLUME_UP',
              iconUrl: '/api/icons/volume_up.svg'
            },
            {
              id: 'btn_next_page',
              row: 0,
              col: 3,
              label: 'Próx. Pág >',
              labelColor: '#FFFFFF',
              backgroundColor: '#89B4FA',
              actionType: 'SWITCH_PAGE',
              actionPayload: { pageIndex: 1 }
            }
          ]
        },
        {
          pageIndex: 1,
          buttons: [
            {
              id: 'btn_prev_page',
              row: 0,
              col: 0,
              label: '< Voltar Pág',
              labelColor: '#FFFFFF',
              backgroundColor: '#89B4FA',
              actionType: 'SWITCH_PAGE',
              actionPayload: { pageIndex: 0 }
            },
            {
              id: 'btn_open_url',
              row: 0,
              col: 1,
              label: 'Abrir YouTube',
              labelColor: '#FFFFFF',
              backgroundColor: '#E74C3C',
              actionType: 'OPEN_URL',
              actionPayload: { url: 'https://youtube.com' }
            }
          ]
        }
      ]
    },
    {
      id: 'streaming',
      name: 'Perfil OBS / Live',
      gridConfig: { rows: 3, cols: 4 },
      pages: [
        {
          pageIndex: 0,
          buttons: [
            {
              id: 'btn_obs_scene1',
              row: 0,
              col: 0,
              label: 'Cena Principal',
              labelColor: '#FFFFFF',
              backgroundColor: '#9B59B6',
              iconUrl: '/api/icons/obs_logo.svg',
              actionType: 'OBS_SCENE',
              actionPayload: { sceneName: 'Principal' }
            }
          ]
        }
      ]
    }
  ]
};

export class ProfileStore {
  private filePath: string;
  private config: AppConfig;

  constructor(filePath: string = DEFAULT_CONFIG_PATH) {
    this.filePath = filePath;
    this.config = this.load();
  }

  private load(): AppConfig {
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      if (fs.existsSync(this.filePath)) {
        const raw = fs.readFileSync(this.filePath, 'utf-8');
        return JSON.parse(raw);
      }
    } catch (err) {
      console.error('[ProfileStore] Erro ao carregar configurações:', err);
    }

    this.saveConfig(DEFAULT_CONFIG);
    return DEFAULT_CONFIG;
  }

  public save(): void {
    this.saveConfig(this.config);
  }

  private saveConfig(cfg: AppConfig): void {
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.filePath, JSON.stringify(cfg, null, 2), 'utf-8');
    } catch (err) {
      console.error('[ProfileStore] Erro ao salvar configurações:', err);
    }
  }

  public getConfig(): AppConfig {
    return this.config;
  }

  public getActiveProfile(): Profile | undefined {
    return this.config.profiles.find((p) => p.id === this.config.activeProfileId);
  }

  public getActivePageButtons(): ButtonModel[] {
    const profile = this.getActiveProfile();
    if (!profile) return [];
    const page = profile.pages.find((p) => p.pageIndex === this.config.activePageIndex);
    return page ? page.buttons : [];
  }

  public setActiveProfile(profileId: string): boolean {
    const exists = this.config.profiles.some((p) => p.id === profileId);
    if (exists) {
      this.config.activeProfileId = profileId;
      this.config.activePageIndex = 0;
      this.save();
      return true;
    }
    return false;
  }

  public setActivePage(pageIndex: number): boolean {
    const profile = this.getActiveProfile();
    if (profile && profile.pages.some((p) => p.pageIndex === pageIndex)) {
      this.config.activePageIndex = pageIndex;
      this.save();
      return true;
    }
    return false;
  }

  public createProfile(id: string, name: string): Profile {
    const newProfile: Profile = {
      id,
      name,
      gridConfig: { rows: 3, cols: 4 },
      pages: [{ pageIndex: 0, buttons: [] }]
    };
    this.config.profiles.push(newProfile);
    this.setActiveProfile(id);
    return newProfile;
  }

  public addPageToActiveProfile(): number {
    const profile = this.getActiveProfile();
    if (!profile) return 0;
    const newPageIndex = profile.pages.length;
    profile.pages.push({ pageIndex: newPageIndex, buttons: [] });
    this.save();
    return newPageIndex;
  }

  public updateButton(profileId: string, pageIndex: number, button: ButtonModel): void {
    const profile = this.config.profiles.find((p) => p.id === profileId);
    if (!profile) return;

    let page = profile.pages.find((p) => p.pageIndex === pageIndex);
    if (!page) {
      page = { pageIndex, buttons: [] };
      profile.pages.push(page);
    }

    const idx = page.buttons.findIndex((b) => b.id === button.id);
    if (idx >= 0) {
      page.buttons[idx] = button;
    } else {
      page.buttons.push(button);
    }

    this.save();
  }
}
