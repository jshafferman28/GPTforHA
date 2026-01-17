/**
 * ChatGPT Client - Playwright Browser Automation
 * Handles all interactions with the ChatGPT web interface
 */

import { chromium } from 'playwright';
import fs from 'fs/promises';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

const CHATGPT_URL = 'https://chatgpt.com';
const LOGIN_URL = 'https://chatgpt.com/auth/login';
const SESSION_API_URL = 'https://chatgpt.com/api/auth/session';
const RESPONSE_TIMEOUT_MS = Number(process.env.RESPONSE_TIMEOUT_MS) || 180000;

// Selectors for ChatGPT interface (may need updates as UI changes)
const SELECTORS = {
    // Login detection
    loginButton: 'button[data-testid="login-button"]',
    userMenu: '[data-testid="profile-button"]',

    // Chat interface
    messageInput: '#prompt-textarea',
    sendButton: 'button[data-testid="send-button"], button[aria-label="Send message"], button[aria-label="Send prompt"]',

    // Response detection
    assistantMessage: 'article[data-testid="conversation-turn"][data-message-author-role="assistant"]',
    assistantMessageFallback: '[data-message-author-role="assistant"]',
    streamingIndicator: '[data-testid="stop-button"], button[aria-label="Stop generating"]',
    regenerateButton: 'button[data-testid="regenerate-button"], button[aria-label="Regenerate"]',
    userMessage: 'article[data-testid="conversation-turn"][data-message-author-role="user"]',
    userMessageFallback: '[data-message-author-role="user"]',

    // New conversation
    newChatButton: 'a[href="/"]',

    // Alternative selectors (fallbacks)
    textareaFallback: 'textarea',
    sendButtonFallback: 'button[type="submit"]',
};

export class ChatGPTClient {
    constructor(options = {}) {
        this.headless = options.headless ?? true;
        this.sessionDir = options.sessionDir || './session';
        this.executablePath = options.executablePath || process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || null;
        this.browser = null;
        this.context = null;
        this.page = null;
        this.isLoggedIn = false;
        this.currentConversationId = null;
    }

    /**
     * Initialize the browser and restore session if available
     */
    async initialize() {
        // Ensure session directory exists
        await fs.mkdir(this.sessionDir, { recursive: true });

        const sessionPath = path.join(this.sessionDir, 'browser-state.json');
        const hasSession = await this._fileExists(sessionPath);

        const executablePath = await this._resolveExecutablePath();

        const launchOptions = {
            headless: this.headless,
            args: [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ],
        };

        if (executablePath) {
            launchOptions.executablePath = executablePath;
            console.log(`Using system Chromium at ${executablePath}`);
        }

        // Launch browser
        this.browser = await chromium.launch(launchOptions);

        // Create context with session state if available
        const contextOptions = {
            viewport: { width: 1280, height: 720 },
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        };

        if (hasSession) {
            try {
                contextOptions.storageState = sessionPath;
                console.log('Restoring session from storage...');
            } catch (error) {
                console.warn('Failed to restore session:', error.message);
            }
        }

        this.context = await this.browser.newContext(contextOptions);
        this.page = await this.context.newPage();

        // Navigate to ChatGPT
        await this.page.goto(CHATGPT_URL, { waitUntil: 'domcontentloaded' });

        // Check login status
        await this._checkLoginStatus();

        if (this.isLoggedIn) {
            console.log('Successfully logged in!');
        } else {
            console.log('Not logged in. Use /api/login to authenticate.');
        }
    }

    /**
     * Check if user is logged in
     */
    async _checkLoginStatus() {
        try {
            // Wait a bit for page to settle
            await this.page.waitForTimeout(2000);

            const apiLogin = await this._checkLoginStatusViaApi();
            if (apiLogin !== null) {
                this.isLoggedIn = apiLogin;
                return;
            }

            // Look for user menu (indicates logged in)
            const userMenu = await this.page.$(SELECTORS.userMenu);
            if (userMenu) {
                this.isLoggedIn = true;
                return;
            }

            // Look for login button (indicates not logged in)
            const loginButton = await this.page.$(SELECTORS.loginButton);
            if (loginButton) {
                this.isLoggedIn = false;
                return;
            }

            // Check for chat input (another indicator of logged in)
            const chatInput = await this.page.$(SELECTORS.messageInput);
            if (chatInput) {
                this.isLoggedIn = true;
                return;
            }

            // Default to not logged in
            this.isLoggedIn = false;
        } catch (error) {
            console.error('Error checking login status:', error);
            this.isLoggedIn = false;
        }
    }

    async _checkLoginStatusViaApi() {
        try {
            const response = await this.context.request.get(SESSION_API_URL, {
                timeout: 10000,
            });

            if (!response.ok()) {
                return false;
            }

            const data = await response.json();
            return Boolean(data?.user?.email || data?.user?.id);
        } catch (error) {
            console.warn('Failed to check session API:', error.message);
            return null;
        }
    }

    /**
     * Get current status
     */
    async getStatus() {
        await this._checkLoginStatus();
        return {
            isLoggedIn: this.isLoggedIn,
            conversationId: this.currentConversationId,
            headless: this.headless,
        };
    }

    /**
     * Open login page for manual authentication
     */
    async openLoginPage() {
        if (this.headless) {
            return {
                success: false,
                message: 'Cannot open login page in headless mode. Restart with HEADLESS=false',
                instruction: 'Set HEADLESS=false environment variable and restart the container',
            };
        }

        await this.page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded' });

        return {
            success: true,
            message: 'Login page opened. Please log in manually, then call /api/login/complete',
            url: LOGIN_URL,
        };
    }

    /**
     * Check if login is complete and save session
     */
    async checkLoginComplete() {
        await this._checkLoginStatus();

        if (this.isLoggedIn) {
            // Save session state
            const sessionPath = path.join(this.sessionDir, 'browser-state.json');
            await this.context.storageState({ path: sessionPath });

            return {
                success: true,
                message: 'Login successful! Session saved.',
            };
        }

        return {
            success: false,
            message: 'Not logged in yet. Please complete the login process.',
        };
    }

    /**
     * Send a message to ChatGPT and get the response
     */
    async sendMessage(message, conversationId = null) {
        await this._checkLoginStatus();
        if (!this.isLoggedIn) {
            throw new Error('Not logged in. Please authenticate first.');
        }

        // If different conversation, navigate to it
        if (conversationId && conversationId !== this.currentConversationId) {
            await this.page.goto(`${CHATGPT_URL}/c/${conversationId}`, { waitUntil: 'domcontentloaded' });
            this.currentConversationId = conversationId;
            await this.page.waitForTimeout(1000);
        }

        const baseline = await this._snapshotAssistantMessages();
        const userBaseline = await this._snapshotUserMessages();
        const networkPromise = this._waitForNetworkResponse(RESPONSE_TIMEOUT_MS).catch((error) => {
            console.warn('Network response capture failed:', error.message);
            return null;
        });

        // Find the message input
        const input = await this._findMessageInput();

        if (!input) {
            throw new Error('Could not find message input field');
        }

        // Clear any existing text and type the message
        await input.click();
        await input.fill('');
        if (message.length > 500) {
            await input.fill(message);
        } else {
            await input.type(message, { delay: 8 });
        }

        // Small delay before sending
        await this.page.waitForTimeout(300);

        // Find and click send button
        let sendButton = await this.page.$(SELECTORS.sendButton);
        if (!sendButton) {
            sendButton = await this.page.$(SELECTORS.sendButtonFallback);
        }

        if (sendButton) {
            const isDisabled = await sendButton.evaluate(
                (el) => el.disabled || el.getAttribute('aria-disabled') === 'true'
            );
            if (!isDisabled) {
                await sendButton.click();
            } else {
                await input.press('Enter');
            }
        } else {
            // Try pressing Enter as fallback
            await input.press('Enter');
        }

        const posted = await this._waitForSendConfirmation(userBaseline, message);
        if (!posted) {
            console.warn('Send did not register, retrying Enter key');
            await input.focus();
            await input.press('Enter');
            const postedAfterRetry = await this._waitForSendConfirmation(userBaseline, message, 8000);
            if (!postedAfterRetry) {
                throw new Error('Failed to submit message to ChatGPT');
            }
        }

        // Wait for response
        const response = await this._waitForAssistantResponse({
            baseline,
            timeout: RESPONSE_TIMEOUT_MS,
            networkPromise,
        });

        // Extract conversation ID from URL if not set
        if (!this.currentConversationId) {
            const url = this.page.url();
            const match = url.match(/\/c\/([a-f0-9-]+)/);
            if (match) {
                this.currentConversationId = match[1];
            } else {
                this.currentConversationId = uuidv4();
            }
        }

        return {
            success: true,
            message: response,
            conversationId: this.currentConversationId,
        };
    }

    /**
     * Wait for ChatGPT to finish responding
     */
    async _waitForResponse({ baseline, timeout = RESPONSE_TIMEOUT_MS } = {}) {
        const startTime = Date.now();
        const stableCyclesRequired = 5;
        let stableCycles = 0;
        let noStreamCycles = 0;
        let hasResponseStarted = false;

        const initialSnapshot = baseline || (await this._snapshotAssistantMessages());
        const baselineCount = initialSnapshot.count;
        const baselineText = initialSnapshot.text;
        let lastText = baselineText;

        while (Date.now() - startTime < timeout) {
            const messages = await this._getAssistantMessages();
            const currentCount = messages.length;
            const currentText = await this._getLastMessageText(messages);
            const streamingIndicator = await this.page.$(SELECTORS.streamingIndicator);
            const regenerateButton = await this.page.$(SELECTORS.regenerateButton);

            if (!hasResponseStarted) {
                if (currentCount > baselineCount || (currentText && currentText !== baselineText)) {
                    hasResponseStarted = true;
                    lastText = currentText || lastText;
                }
            } else if (currentText) {
                if (currentText === lastText) {
                    stableCycles += 1;
                } else {
                    stableCycles = 0;
                    lastText = currentText;
                }

                if (!streamingIndicator || regenerateButton) {
                    noStreamCycles += 1;
                } else {
                    noStreamCycles = 0;
                }

                if (noStreamCycles >= 2 && currentText) {
                    return currentText.trim();
                }

                if (stableCycles >= stableCyclesRequired) {
                    if (!streamingIndicator || regenerateButton || stableCycles >= stableCyclesRequired + 2) {
                        return currentText.trim();
                    }
                }
            }

            await this.page.waitForTimeout(500);
        }

        if (hasResponseStarted && lastText) {
            console.warn('Timeout waiting for response; returning last assistant message');
            return lastText.trim();
        }

        throw new Error('Timeout waiting for response');
    }

    async _waitForAssistantResponse({ baseline, timeout, networkPromise } = {}) {
        const domPromise = this._waitForResponse({ baseline, timeout }).catch((error) => {
            console.warn('DOM response capture failed:', error.message);
            return null;
        });
        const networkSafe = networkPromise || Promise.resolve(null);

        const first = await Promise.race([domPromise, networkSafe]);
        if (first) {
            return first;
        }

        const [domResult, networkResult] = await Promise.all([domPromise, networkSafe]);
        if (domResult) {
            return domResult;
        }
        if (networkResult) {
            return networkResult;
        }

        throw new Error('Failed to capture assistant response');
    }

    async _snapshotAssistantMessages() {
        const messages = await this._getAssistantMessages();
        return {
            count: messages.length,
            text: await this._getLastMessageText(messages),
        };
    }

    async _snapshotUserMessages() {
        const messages = await this._getUserMessages();
        return {
            count: messages.length,
            text: await this._getLastUserMessageText(messages),
        };
    }

    async _getAssistantMessages() {
        let messages = await this.page.$$(SELECTORS.assistantMessage);
        if (!messages.length) {
            messages = await this.page.$$(SELECTORS.assistantMessageFallback);
        }
        return messages;
    }

    async _getUserMessages() {
        let messages = await this.page.$$(SELECTORS.userMessage);
        if (!messages.length) {
            messages = await this.page.$$(SELECTORS.userMessageFallback);
        }
        return messages;
    }

    async _getLastMessageText(messages) {
        if (!messages.length) {
            return '';
        }
        const lastMessage = messages[messages.length - 1];
        try {
            const markdown = await lastMessage.$('.markdown');
            if (markdown) {
                const text = await markdown.innerText();
                return text ? text.trim() : '';
            }
        } catch {
            // Fall back to generic text extraction.
        }
        const text = await lastMessage.innerText();
        return text ? text.trim() : '';
    }

    async _waitForNetworkResponse(timeout) {
        const response = await this.page.waitForResponse(
            (resp) => {
                const url = resp.url();
                if (!url.includes('/backend-api/conversation')) {
                    return false;
                }
                const request = resp.request();
                if (request.method() !== 'POST') {
                    return false;
                }
                return true;
            },
            { timeout }
        );

        const text = await response.text();
        const payload = this._extractAssistantFromSse(text);
        console.log('Captured assistant response from network stream');
        if (payload.conversationId) {
            this.currentConversationId = payload.conversationId;
        }
        if (!payload.text) {
            throw new Error('No assistant message in network response');
        }
        return payload.text;
    }

    _extractAssistantFromSse(raw) {
        const lines = raw.split('\n');
        let latestText = '';
        let conversationId = null;

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data:')) {
                continue;
            }
            const payload = trimmed.slice(5).trim();
            if (!payload || payload === '[DONE]') {
                continue;
            }
            try {
                const data = JSON.parse(payload);
                conversationId = data.conversation_id || data.conversationId || conversationId;
                const message = data.message;
                if (message && message.author && message.author.role === 'assistant') {
                    const content = message.content || {};
                    const parts = Array.isArray(content.parts) ? content.parts : [];
                    const text = parts.filter((part) => typeof part === 'string').join('\n').trim();
                    if (text) {
                        latestText = text;
                    }
                }
            } catch {
                // Ignore malformed lines.
            }
        }

        return { text: latestText, conversationId };
    }

    async _getLastUserMessageText(messages) {
        return this._getLastMessageText(messages);
    }

    async _waitForSendConfirmation(baseline, message, timeout = 10000) {
        const startTime = Date.now();
        const prefix = message.trim().slice(0, 40);
        while (Date.now() - startTime < timeout) {
            const userMessages = await this._getUserMessages();
            const lastUserText = await this._getLastUserMessageText(userMessages);
            const streamingIndicator = await this.page.$(SELECTORS.streamingIndicator);
            const regenerateButton = await this.page.$(SELECTORS.regenerateButton);

            if (userMessages.length > baseline.count) {
                return true;
            }

            if (prefix && lastUserText && lastUserText.includes(prefix)) {
                return true;
            }

            if (streamingIndicator || regenerateButton) {
                return true;
            }

            await this.page.waitForTimeout(300);
        }

        return false;
    }

    async _findMessageInput(timeout = 15000) {
        const selectors = [SELECTORS.messageInput, SELECTORS.textareaFallback];
        for (const selector of selectors) {
            try {
                const handle = await this.page.waitForSelector(selector, {
                    state: 'visible',
                    timeout,
                });
                if (handle) {
                    return handle;
                }
            } catch {
                // Try next selector
            }
        }
        return null;
    }

    /**
     * Start a new conversation
     */
    async newConversation() {
        await this._checkLoginStatus();
        if (!this.isLoggedIn) {
            throw new Error('Not logged in. Please authenticate first.');
        }

        // Navigate to home page for new conversation
        await this.page.goto(CHATGPT_URL, { waitUntil: 'domcontentloaded' });
        await this.page.waitForTimeout(1000);

        this.currentConversationId = null;

        return {
            success: true,
            message: 'New conversation started',
        };
    }

    /**
     * Close the browser
     */
    async close() {
        if (this.context) {
            // Save session before closing
            try {
                const sessionPath = path.join(this.sessionDir, 'browser-state.json');
                await this.context.storageState({ path: sessionPath });
                console.log('Session saved');
            } catch (error) {
                console.warn('Failed to save session:', error.message);
            }
        }

        if (this.browser) {
            await this.browser.close();
            this.browser = null;
            this.context = null;
            this.page = null;
        }
    }

    /**
     * Clear persisted session data and cookies
     */
    async clearSession() {
        this.isLoggedIn = false;
        this.currentConversationId = null;

        if (this.context) {
            try {
                await this.context.clearCookies();
            } catch (error) {
                console.warn('Failed to clear cookies:', error.message);
            }
        }

        const sessionPath = path.join(this.sessionDir, 'browser-state.json');
        try {
            await fs.rm(sessionPath, { force: true });
            console.log('Session file removed');
        } catch (error) {
            console.warn('Failed to remove session file:', error.message);
        }
    }

    /**
     * Check if a file exists
     */
    async _fileExists(filePath) {
        try {
            await fs.access(filePath);
            return true;
        } catch {
            return false;
        }
    }

    async _resolveExecutablePath() {
        const candidates = [
            this.executablePath,
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
        ];

        for (const candidate of candidates) {
            if (!candidate) {
                continue;
            }
            try {
                await fs.access(candidate);
                return candidate;
            } catch {
                // Try next candidate
            }
        }

        return null;
    }
}
