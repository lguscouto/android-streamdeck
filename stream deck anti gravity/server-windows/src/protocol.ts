export enum EventTypes {
  PRESS_BUTTON = 'PRESS_BUTTON',
  RELEASE_BUTTON = 'RELEASE_BUTTON',
  SWITCH_PAGE = 'SWITCH_PAGE',
  SWITCH_PROFILE = 'SWITCH_PROFILE',
  OPEN_FOLDER = 'OPEN_FOLDER',
  GO_BACK_FOLDER = 'GO_BACK_FOLDER',
  PING = 'PING',
  PONG = 'PONG',
  GRID_SYNC = 'GRID_SYNC',
  BUTTON_STATE_CHANGE = 'BUTTON_STATE_CHANGE',
  HARDWARE_SYNC = 'HARDWARE_SYNC',
  SPOTIFY_SYNC = 'SPOTIFY_SYNC'
}

export interface WebSocketMessage<T = any> {
  event: EventTypes | string;
  payload: T;
}

export interface PressButtonPayload {
  profileId: string;
  pageIndex: number;
  row: number;
  col: number;
  buttonId: string;
  actionType?: string;
}

export interface ButtonStateModel {
  label: string;
  iconUrl?: string;
  backgroundColor?: string;
}

export interface ButtonModel {
  id: string;
  row: number;
  col: number;
  rowSpan?: number;
  colSpan?: number;
  label: string;
  labelColor?: string;
  backgroundColor?: string;
  iconUrl?: string;
  state?: string;
  states?: Record<string, ButtonStateModel>;
  actionType?: string;
  actionPayload?: Record<string, any>;
  folderButtons?: ButtonModel[];
}

export interface GridConfig {
  rows: number;
  cols: number;
}

export interface GridSyncPayload {
  activeProfileId: string;
  activePageIndex: number;
  currentFolderId?: string;
  folderPath?: string[];
  gridConfig: GridConfig;
  buttons: ButtonModel[];
}

export interface ButtonStateChangePayload {
  buttonId: string;
  newState: string;
}

export interface HardwareMetricsPayload {
  cpuUsage: number;
  cpuTemp: number;
  ramUsage: number;
  ramUsedGb: string;
  ramTotalGb: string;
  gpuUsage: number;
}

export interface SpotifyTrackPayload {
  title: string;
  artist: string;
  isPlaying: boolean;
}
