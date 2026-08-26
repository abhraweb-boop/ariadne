// electron/main.ts
import { app, BrowserWindow, ipcMain } from "electron";
import { existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
var __dirname = dirname(fileURLToPath(import.meta.url));
function resolveGatewayBase() {
  const fromEnv = process.env.PRIME_GATEWAY_BASE;
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  const stamp = join(__dirname, "..", "install-stamp.json");
  try {
    if (existsSync(stamp)) {
      const data = JSON.parse(readFileSync(stamp, "utf-8"));
      if (data?.gatewayBase) return String(data.gatewayBase).replace(/\/+$/, "");
    }
  } catch {
  }
  return "http://127.0.0.1:8000";
}
function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    title: "Prime Hermes",
    backgroundColor: "#101012",
    webPreferences: {
      preload: join(__dirname, "..", "dist", "electron-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  const devServer = process.env.HERMES_DESKTOP_DEV_SERVER;
  if (devServer) {
    void win.loadURL(devServer);
  } else {
    void win.loadFile(join(__dirname, "..", "dist", "index.html"));
  }
  return win;
}
app.whenReady().then(() => {
  const gatewayBase = resolveGatewayBase();
  ipcMain.handle("prime:gateway-base", () => gatewayBase);
  ipcMain.handle("prime:platform", () => process.platform);
  ipcMain.handle("prime:versions", () => ({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  }));
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
//# sourceMappingURL=electron-main.mjs.map
