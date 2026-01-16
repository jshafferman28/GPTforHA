/**
 * ChatGPT Sidecar - Express API Server
 * Provides REST API for ChatGPT browser automation
 */

import express from 'express';
import { ChatGPTClient } from './chatgpt-client.js';

const app = express();
app.use(express.json());

// Configuration
const PORT = process.env.PORT || 3000;
const HEADLESS = process.env.HEADLESS !== 'false';
const SESSION_DIR = process.env.SESSION_DIR || './session';

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

app.listen(PORT, '0.0.0.0', () => {
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
