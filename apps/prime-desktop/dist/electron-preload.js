"use strict";

// electron/preload.ts
var import_electron = require("electron");
import_electron.contextBridge.exposeInMainWorld("primeHermes", {
  gatewayBase: () => import_electron.ipcRenderer.invoke("prime:gateway-base"),
  platform: () => import_electron.ipcRenderer.invoke("prime:platform"),
  versions: () => import_electron.ipcRenderer.invoke("prime:versions")
});
