const electron = require('electron');
const path = require('path');

// Debug: log what electron contains
console.log('electron keys:', Object.keys(electron));
console.log('electron.app:', electron.app);
console.log('electron type:', typeof electron);

const { app, BrowserWindow } = electron;

if (!app) {
  console.error('ERROR: app is undefined. Trying default export...');
  const mod = electron.default || electron;
  console.log('default keys:', Object.keys(mod));
  process.exit(1);
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
