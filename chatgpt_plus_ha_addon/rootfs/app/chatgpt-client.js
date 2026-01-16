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

// Selectors for ChatGPT interface (may need updates as UI changes)
const SELECTORS = {
    // Login detection
    loginButton: 'button[data-testid="login-button"]',
    userMenu: '[data-testid="profile-button"]',

    // Chat interface
    messageInput: '#prompt-textarea',
    sendButton: 'button[data-testid="send-button"]',

    // Response detection
    assistantMessage: '[data-message-author-role="assistant"]',
    streamingIndicator: '[data-testid="stop-button"]',

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

        // Launch browser
        this.browser = await chromium.launch({
            headless: this.headless,
            args: [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ],
        });

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
        if (!this.isLoggedIn) {
            throw new Error('Not logged in. Please authenticate first.');
        }

        // If different conversation, navigate to it
        if (conversationId && conversationId !== this.currentConversationId) {
            await this.page.goto(`${CHATGPT_URL}/c/${conversationId}`, { waitUntil: 'domcontentloaded' });
            this.currentConversationId = conversationId;
            await this.page.waitForTimeout(1000);
        }

        // Find the message input
        let input = await this.page.$(SELECTORS.messageInput);
        if (!input) {
            input = await this.page.$(SELECTORS.textareaFallback);
        }

        if (!input) {
            throw new Error('Could not find message input field');
        }

        // Clear any existing text and type the message
        await input.click();
        await input.fill(message);

        // Small delay before sending
        await this.page.waitForTimeout(300);

        // Find and click send button
        let sendButton = await this.page.$(SELECTORS.sendButton);
        if (!sendButton) {
            sendButton = await this.page.$(SELECTORS.sendButtonFallback);
        }

        if (sendButton) {
            await sendButton.click();
        } else {
            // Try pressing Enter as fallback
            await input.press('Enter');
        }

        // Wait for response
        const response = await this._waitForResponse();

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
    async _waitForResponse(timeout = 120000) {
        const startTime = Date.now();
        let lastMessageCount = 0;
        let stableCount = 0;

        while (Date.now() - startTime < timeout) {
            // Check if still streaming
            const streamingIndicator = await this.page.$(SELECTORS.streamingIndicator);

            if (!streamingIndicator) {
                // No streaming indicator, might be done
                // Wait a bit and check for stable message
                await this.page.waitForTimeout(500);

                const messages = await this.page.$$(SELECTORS.assistantMessage);

                if (messages.length > 0) {
                    const currentCount = messages.length;

                    if (currentCount === lastMessageCount) {
                        stableCount++;
                        if (stableCount >= 3) {
                            // Message is stable, get the last one
                            const lastMessage = messages[messages.length - 1];
                            const text = await lastMessage.textContent();
                            return text?.trim() || '';
                        }
                    } else {
                        stableCount = 0;
                        lastMessageCount = currentCount;
                    }
                }
            }

            await this.page.waitForTimeout(500);
        }

        throw new Error('Timeout waiting for response');
    }

    /**
     * Start a new conversation
     */
    async newConversation() {
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
}
