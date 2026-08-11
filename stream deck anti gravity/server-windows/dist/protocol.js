"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EventTypes = void 0;
var EventTypes;
(function (EventTypes) {
    EventTypes["PRESS_BUTTON"] = "PRESS_BUTTON";
    EventTypes["RELEASE_BUTTON"] = "RELEASE_BUTTON";
    EventTypes["SWITCH_PAGE"] = "SWITCH_PAGE";
    EventTypes["SWITCH_PROFILE"] = "SWITCH_PROFILE";
    EventTypes["OPEN_FOLDER"] = "OPEN_FOLDER";
    EventTypes["GO_BACK_FOLDER"] = "GO_BACK_FOLDER";
    EventTypes["PING"] = "PING";
    EventTypes["PONG"] = "PONG";
    EventTypes["GRID_SYNC"] = "GRID_SYNC";
    EventTypes["BUTTON_STATE_CHANGE"] = "BUTTON_STATE_CHANGE";
    EventTypes["HARDWARE_SYNC"] = "HARDWARE_SYNC";
    EventTypes["SPOTIFY_SYNC"] = "SPOTIFY_SYNC";
})(EventTypes || (exports.EventTypes = EventTypes = {}));
