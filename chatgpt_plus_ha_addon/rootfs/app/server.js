/**
 * ChatGPT Sidecar - Express API Server
 * Provides REST API for ChatGPT browser automation
 */

import express from 'express';
import fs from 'fs/promises';
import http from 'http';
import net from 'net';
import path from 'path';
import { fileURLToPath } from 'url';
import { WebSocketServer } from 'ws';
import { ChatGPTClient } from './chatgpt-client.js';

const app = express();
app.use(express.json());

const stripIngressPath = (urlPath, ingressPath) => {
  if (!ingressPath || typeof ingressPath !== 'string') {
    return urlPath;
  }
  if (urlPath.startsWith(ingressPath)) {
    const stripped = urlPath.slice(ingressPath.length);
    return stripped.length ? stripped : '/';
  }
  return urlPath;
};

app.use((req, res, next) => {
  const ingressPath = req.headers['x-ingress-path'];
  if (ingressPath) {
    req.url = stripIngressPath(req.url, ingressPath);
  } else if (req.url.includes('/api/hassio_ingress/')) {
    const tokenIndex = req.url.indexOf('/api/hassio_ingress/');
    if (tokenIndex >= 0) {
      const afterToken = req.url.slice(tokenIndex + '/api/hassio_ingress/'.length);
      const nextSlash = afterToken.indexOf('/');
      if (nextSlash >= 0) {
        const rewritten = afterToken.slice(nextSlash);
        req.url = rewritten.length ? rewritten : '/';
      }
    }
  }
  next();
});

// Configuration
const PORT = process.env.PORT || 3000;
const HEADLESS = process.env.HEADLESS !== 'false';
const SESSION_DIR = process.env.SESSION_DIR || './session';
const VNC_HOST = process.env.VNC_HOST || '127.0.0.1';
const VNC_PORT = Number(process.env.VNC_PORT || 5900);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const novncPath = path.resolve(__dirname, 'node_modules', '@novnc', 'novnc');

app.use('/novnc', express.static(novncPath));

async function _logNoVncStatus() {
  try {
    await fs.access(path.join(novncPath, 'core', 'rfb.js'));
    console.log('noVNC assets found');
  } catch (error) {
    console.warn('noVNC assets not found:', error.message);
  }
}

// Initialize ChatGPT client
const chatgptClient = new ChatGPTClient({
  headless: HEADLESS,
  sessionDir: SESSION_DIR,
});

// Track initialization status
let isInitialized = false;
let initError = null;

// Initialize client on startup
(async () => {
  try {
    console.log('Initializing ChatGPT client...');
    console.log(`  Headless: ${HEADLESS}`);
    console.log(`  Session Dir: ${SESSION_DIR}`);
    await chatgptClient.initialize();
    isInitialized = true;
    console.log('ChatGPT client initialized successfully');
  } catch (error) {
    initError = error;
    console.error('Failed to initialize ChatGPT client:', error);
  }
})();

// Middleware to check initialization
const checkInitialized = (req, res, next) => {
  if (!isInitialized) {
    return res.status(503).json({
      error: 'Service not ready',
      message: initError ? initError.message : 'Still initializing...',
    });
  }
  next();
};

// Root endpoint for ingress UI
app.get('/', async (req, res) => {
  if (!isInitialized) {
    return res.status(503).send('ChatGPT Plus HA sidecar is starting...');
  }

  try {
    const status = await chatgptClient.getStatus();
    const loginState = status.isLoggedIn ? 'Logged in' : 'Not logged in';
    const headlessState = HEADLESS ? 'true' : 'false';

    res.setHeader('Content-Type', 'text/html');
    res.send(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ChatGPT Plus HA</title>
  <style>
    body { font-family: sans-serif; padding: 24px; line-height: 1.5; }
    code { background: #f2f2f2; padding: 2px 4px; border-radius: 4px; }
    button { padding: 8px 12px; margin-right: 8px; }
    .status { margin-top: 16px; white-space: pre-wrap; background: #f7f7f7; padding: 12px; border-radius: 6px; }
  </style>
</head>
<body>
  <h1>ChatGPT Plus HA Sidecar</h1>
  <p>Status: <strong>${loginState}</strong></p>
  <p>Headless: <strong>${headlessState}</strong></p>
  <p>Health: <a id="healthLink" href="#">/health</a></p>
  <p>Status API: <a id="statusLink" href="#">/api/status</a></p>
  <p>Login: <a id="loginLink" href="#">/api/login</a></p>
  <p>After login completes, call <code>/api/login/complete</code>.</p>
  <p>If you are not logged in, set <code>headless: false</code> in the add-on config, restart, and open the login endpoint.</p>
  <div>
    <button id="loginBtn">Start login</button>
    <button id="loginCompleteBtn">Complete login</button>
    <button id="openViewerBtn">Open login viewer</button>
    <button id="clearSessionBtn">Clear session</button>
  </div>
  <div class="status" id="statusBox">Ready.</div>
  <script>
    const statusBox = document.getElementById('statusBox');
    const baseHref = window.location.href.endsWith('/') ? window.location.href : window.location.href + '/';
    const buildUrl = (path) => new URL(path, baseHref).toString();

    const healthUrl = buildUrl('health');
    const statusUrl = buildUrl('api/status');
    const loginUrl = buildUrl('api/login');
    const loginCompleteUrl = buildUrl('api/login/complete');

    document.getElementById('healthLink').href = healthUrl;
    document.getElementById('statusLink').href = statusUrl;
    document.getElementById('loginLink').href = loginUrl;

    const showStatus = (data) => {
      statusBox.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    };
    const parseResponse = async (response) => {
      const text = await response.text();
      try {
        return JSON.parse(text);
      } catch (err) {
        return text || response.statusText;
      }
    };
    document.getElementById('loginBtn').addEventListener('click', async () => {
      showStatus('Calling /api/login...');
      try {
        const response = await fetch(loginUrl);
        const payload = await parseResponse(response);
        showStatus(payload);
      } catch (err) {
        showStatus(err.message || String(err));
      }
    });
    document.getElementById('openViewerBtn').addEventListener('click', () => {
      window.open(buildUrl('vnc'), '_blank', 'noopener');
    });
    document.getElementById('loginCompleteBtn').addEventListener('click', async () => {
      showStatus('Calling /api/login/complete...');
      try {
        const response = await fetch(loginCompleteUrl, { method: 'POST' });
        const payload = await parseResponse(response);
        showStatus(payload);
      } catch (err) {
        showStatus(err.message || String(err));
      }
    });
    document.getElementById('clearSessionBtn').addEventListener('click', async () => {
      showStatus('Clearing session...');
      try {
        const response = await fetch(buildUrl('api/session/clear'), { method: 'POST' });
        const payload = await parseResponse(response);
        showStatus(payload);
      } catch (err) {
        showStatus(err.message || String(err));
      }
    });
  </script>
</body>
</html>`);
  } catch (error) {
    res.status(500).send(`Error fetching status: ${error.message}`);
  }
});

// VNC viewer page
app.get('/vnc', (req, res) => {
  res.setHeader('Content-Type', 'text/html');
  res.send(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ChatGPT Plus HA Login Viewer</title>
  <style>
    body { font-family: sans-serif; padding: 16px; }
    #screen { width: 100%; height: 80vh; border: 1px solid #ccc; }
    #status { margin-top: 12px; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>Login Viewer</h1>
  <div id="screen"></div>
  <div id="status">Connecting...</div>
  <script type="module">
    const statusEl = document.getElementById('status');
    const showStatus = (text) => {
      statusEl.textContent = text;
    };

    const buildRfbUrl = () => {
      const baseUrl = new URL(window.location.href);
      baseUrl.search = '';
      baseUrl.hash = '';
      baseUrl.pathname = baseUrl.pathname.replace(/\\/vnc\\/?$/, '/');
      return new URL('novnc/core/rfb.js', baseUrl).toString();
    };

    const pageUrl = new URL(window.location.href);
    pageUrl.protocol = pageUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    pageUrl.pathname = pageUrl.pathname.replace(/\\/vnc\\/?$/, '/vnc/ws');
    pageUrl.search = '';
    pageUrl.hash = '';
    const wsUrl = pageUrl.toString();

    const loadRfb = (src) => import(src).then((module) => module.default);
    const localRfbUrl = buildRfbUrl();

    loadRfb(localRfbUrl)
      .catch(() => loadRfb('https://cdn.jsdelivr.net/npm/@novnc/novnc@1.4.0/core/rfb.js'))
      .then((RFB) => {
        const rfb = new RFB(document.getElementById('screen'), wsUrl, {
          shared: true,
          scaleViewport: true,
        });

        rfb.addEventListener('connect', () => showStatus('Connected'));
        rfb.addEventListener('disconnect', (event) => {
          const clean = event.detail && event.detail.clean;
          showStatus('Disconnected: ' + (clean ? 'clean' : 'error'));
        });
        rfb.addEventListener('securityfailure', (event) => {
          const status = event.detail && event.detail.status;
          showStatus('Security failure: ' + (status || 'unknown'));
        });
      })
      .catch((error) => {
        showStatus('Failed to load VNC client: ' + (error.message || error));
      });
  </script>
</body>
</html>`);
});

// ============================================
// Health & Status Endpoints
// ============================================

/**
 * Health check endpoint
 */
app.get('/health', (req, res) => {
  res.json({
    status: isInitialized ? 'healthy' : 'initializing',
    timestamp: new Date().toISOString(),
  });
});

/**
 * Get authentication status
 */
app.get('/api/status', checkInitialized, async (req, res) => {
  try {
    const status = await chatgptClient.getStatus();
    res.json(status);
  } catch (error) {
    console.error('Error getting status:', error);
    res.status(500).json({
      error: 'Failed to get status',
      message: error.message,
    });
  }
});

// ============================================
// Authentication Endpoints
// ============================================

/**
 * Get login page URL for manual authentication
 * Returns a URL that opens the browser for login
 */
app.get('/api/login', checkInitialized, async (req, res) => {
  try {
    const result = await chatgptClient.openLoginPage();
    res.json(result);
  } catch (error) {
    console.error('Error opening login page:', error);
    res.status(500).json({
      error: 'Failed to open login page',
      message: error.message,
    });
  }
});

/**
 * Check if login is complete and save session
 */
app.post('/api/login/complete', checkInitialized, async (req, res) => {
  try {
    const result = await chatgptClient.checkLoginComplete();
    res.json(result);
  } catch (error) {
    console.error('Error checking login:', error);
    res.status(500).json({
      error: 'Failed to check login status',
      message: error.message,
    });
  }
});

// ============================================
// Chat Endpoints
// ============================================

/**
 * Send a message to ChatGPT
 * POST /api/chat
 * Body: { message: string, conversationId?: string }
 */
app.post('/api/chat', checkInitialized, async (req, res) => {
  try {
    const { message, conversationId } = req.body;

    if (!message || typeof message !== 'string') {
      return res.status(400).json({
        error: 'Invalid request',
        message: 'Message is required and must be a string',
      });
    }

    console.log(`Received chat request: "${message.substring(0, 50)}..."`);

    const response = await chatgptClient.sendMessage(message, conversationId);
    res.json(response);
  } catch (error) {
    console.error('Error sending message:', error);
    res.status(500).json({
      error: 'Failed to send message',
      message: error.message,
    });
  }
});

/**
 * Start a new conversation
 */
app.post('/api/conversation/new', checkInitialized, async (req, res) => {
  try {
    const result = await chatgptClient.newConversation();
    res.json(result);
  } catch (error) {
    console.error('Error creating new conversation:', error);
    res.status(500).json({
      error: 'Failed to create new conversation',
      message: error.message,
    });
  }
});

// ============================================
// Server Startup
// ============================================

const server = http.createServer(app);
const wss = new WebSocketServer({ noServer: true });

wss.on('connection', (ws) => {
  console.log('VNC client connected');
  const vncSocket = net.createConnection(VNC_PORT, VNC_HOST);

  vncSocket.on('connect', () => {
    console.log('Connected to VNC server');
  });

  ws.on('message', (data) => {
    if (vncSocket.writable) {
      vncSocket.write(data);
    }
  });

  vncSocket.on('data', (chunk) => {
    if (ws.readyState === ws.OPEN) {
      ws.send(chunk);
    }
  });

  const closeAll = () => {
    if (!vncSocket.destroyed) {
      vncSocket.destroy();
    }
    if (ws.readyState === ws.OPEN || ws.readyState === ws.CONNECTING) {
      ws.close();
    }
  };

  ws.on('close', closeAll);
  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
    closeAll();
  });
  vncSocket.on('close', closeAll);
  vncSocket.on('error', (error) => {
    console.error('VNC socket error:', error);
    closeAll();
  });
});

app.post('/api/session/clear', checkInitialized, async (req, res) => {
  try {
    await chatgptClient.clearSession();
    res.json({ success: true, message: 'Session cleared' });
  } catch (error) {
    console.error('Error clearing session:', error);
    res.status(500).json({
      error: 'Failed to clear session',
      message: error.message,
    });
  }
});

server.on('upgrade', (req, socket, head) => {
  if (!req.url) {
    socket.destroy();
    return;
  }
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (!url.pathname.endsWith('/vnc/ws') && !url.pathname.endsWith('/vnc')) {
    socket.destroy();
    return;
  }
  wss.handleUpgrade(req, socket, head, (ws) => {
    wss.emit('connection', ws, req);
  });
});

server.listen(PORT, '0.0.0.0', () => {
  _logNoVncStatus();
  console.log(`ChatGPT Sidecar running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('Received SIGTERM, shutting down...');
  await chatgptClient.close();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('Received SIGINT, shutting down...');
  await chatgptClient.close();
  process.exit(0);
});
