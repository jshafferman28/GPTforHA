/**
 * ChatGPT Plus HA - Chat Panel Web Component
 * A modern chat interface for Home Assistant
 */

class ChatGPTPlusPanel extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this._hass = null;
        this._messages = [];
        this._isLoading = false;
    }

    set hass(hass) {
        this._hass = hass;
        if (!this._initialized) {
            this._initialize();
            this._initialized = true;
        }
    }

    _initialize() {
        this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          --chat-bg: var(--primary-background-color, #1a1a2e);
          --message-user-bg: var(--primary-color, #4a90d9);
          --message-assistant-bg: var(--secondary-background-color, #16213e);
          --text-color: var(--primary-text-color, #e8e8e8);
          --input-bg: var(--card-background-color, #0f0f23);
          --border-color: var(--divider-color, #2a2a4a);
          --accent-color: var(--accent-color, #667eea);
        }

        .container {
          display: flex;
          flex-direction: column;
          height: 100%;
          max-height: 100vh;
          background: var(--chat-bg);
          font-family: var(--paper-font-body1_-_font-family, 'Roboto', sans-serif);
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 20px;
          background: linear-gradient(135deg, var(--accent-color), #764ba2);
          color: white;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        }

        .header h1 {
          margin: 0;
          font-size: 20px;
          font-weight: 500;
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .header-icon {
          width: 28px;
          height: 28px;
        }

        .new-chat-btn {
          background: rgba(255, 255, 255, 0.2);
          border: none;
          color: white;
          padding: 8px 16px;
          border-radius: 20px;
          cursor: pointer;
          font-size: 14px;
          transition: background 0.2s;
        }

        .new-chat-btn:hover {
          background: rgba(255, 255, 255, 0.3);
        }

        .messages {
          flex: 1;
          overflow-y: auto;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .message {
          display: flex;
          gap: 12px;
          max-width: 85%;
          animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
          align-self: flex-end;
          flex-direction: row-reverse;
        }

        .message.assistant {
          align-self: flex-start;
        }

        .avatar {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          flex-shrink: 0;
        }

        .message.user .avatar {
          background: var(--message-user-bg);
        }

        .message.assistant .avatar {
          background: var(--accent-color);
        }

        .content {
          padding: 12px 16px;
          border-radius: 18px;
          line-height: 1.5;
          color: var(--text-color);
          word-wrap: break-word;
        }

        .message.user .content {
          background: var(--message-user-bg);
          border-bottom-right-radius: 4px;
        }

        .message.assistant .content {
          background: var(--message-assistant-bg);
          border-bottom-left-radius: 4px;
        }

        .input-area {
          padding: 16px 20px;
          background: var(--input-bg);
          border-top: 1px solid var(--border-color);
        }

        .input-container {
          display: flex;
          gap: 12px;
          align-items: flex-end;
        }

        textarea {
          flex: 1;
          padding: 12px 16px;
          border: 1px solid var(--border-color);
          border-radius: 24px;
          background: var(--chat-bg);
          color: var(--text-color);
          font-size: 15px;
          resize: none;
          min-height: 24px;
          max-height: 150px;
          line-height: 1.4;
          font-family: inherit;
        }

        textarea:focus {
          outline: none;
          border-color: var(--accent-color);
          box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
        }

        textarea::placeholder {
          color: var(--secondary-text-color, #888);
        }

        .send-btn {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          border: none;
          background: var(--accent-color);
          color: white;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: transform 0.2s, background 0.2s;
        }

        .send-btn:hover:not(:disabled) {
          transform: scale(1.05);
          background: #5a6fd6;
        }

        .send-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .loading {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 16px;
          background: var(--message-assistant-bg);
          border-radius: 18px;
          color: var(--text-color);
        }

        .loading-dots {
          display: flex;
          gap: 4px;
        }

        .loading-dots span {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--accent-color);
          animation: bounce 1.4s infinite ease-in-out;
        }

        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: var(--secondary-text-color, #888);
          text-align: center;
          padding: 40px;
        }

        .empty-state svg {
          width: 80px;
          height: 80px;
          margin-bottom: 20px;
          opacity: 0.5;
        }

        .empty-state h2 {
          margin: 0 0 8px;
          font-size: 24px;
          font-weight: 500;
          color: var(--text-color);
        }

        .empty-state p {
          margin: 0;
          font-size: 16px;
        }

        /* Code blocks */
        pre {
          background: #1e1e2e;
          padding: 12px;
          border-radius: 8px;
          overflow-x: auto;
          font-size: 13px;
        }

        code {
          font-family: 'Fira Code', 'Consolas', monospace;
        }
      </style>

      <div class="container">
        <div class="header">
          <h1>
            <svg class="header-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
            </svg>
            ChatGPT Plus
          </h1>
          <button class="new-chat-btn" id="newChatBtn">
            New Chat
          </button>
        </div>

        <div class="messages" id="messages">
          <div class="empty-state" id="emptyState">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
            </svg>
            <h2>Start a conversation</h2>
            <p>Ask ChatGPT anything about your Home Assistant setup</p>
          </div>
        </div>

        <div class="input-area">
          <div class="input-container">
            <textarea 
              id="messageInput" 
              placeholder="Type your message..."
              rows="1"
            ></textarea>
            <button class="send-btn" id="sendBtn">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    `;

        this._setupEventListeners();
    }

    _setupEventListeners() {
        const input = this.shadowRoot.getElementById('messageInput');
        const sendBtn = this.shadowRoot.getElementById('sendBtn');
        const newChatBtn = this.shadowRoot.getElementById('newChatBtn');

        // Auto-resize textarea
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 150) + 'px';
        });

        // Send on Enter (Shift+Enter for new line)
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this._sendMessage();
            }
        });

        // Send button click
        sendBtn.addEventListener('click', () => this._sendMessage());

        // New chat button
        newChatBtn.addEventListener('click', () => this._newConversation());
    }

    async _sendMessage() {
        const input = this.shadowRoot.getElementById('messageInput');
        const message = input.value.trim();

        if (!message || this._isLoading) return;

        const requestId = this._generateRequestId();

        // Add user message
        this._addMessage('user', message);
        input.value = '';
        input.style.height = 'auto';

        // Show loading
        this._isLoading = true;
        this._showLoading();

        try {
            // Call Home Assistant service
            await this._hass.callService('chatgpt_plus_ha', 'send_message', {
                message: message,
                request_id: requestId,
            });

            const response = await this._waitForResponse(requestId);

            this._hideLoading();
            this._addMessage('assistant', response);
        } catch (error) {
            this._hideLoading();
            this._addMessage('assistant', `Error: ${error.message || 'Failed to get response'}`);
        } finally {
            this._isLoading = false;
        }
    }

    async _waitForResponse(requestId) {
        return new Promise((resolve, reject) => {
            let unsubscribe = null;
            const timeout = setTimeout(() => {
                if (unsubscribe) {
                    unsubscribe();
                }
                reject(new Error('Timeout waiting for response'));
            }, 120000);

            const handleEvent = (event) => {
                const data = event?.data || {};
                if (data.request_id && data.request_id !== requestId) {
                    return;
                }
                if (data.response === undefined) {
                    return;
                }
                clearTimeout(timeout);
                if (unsubscribe) {
                    unsubscribe();
                }
                resolve(data.response);
            };

            this._hass.connection
                .subscribeEvents(handleEvent, 'chatgpt_plus_ha_response')
                .then((unsub) => {
                    unsubscribe = unsub;
                })
                .catch((error) => {
                    clearTimeout(timeout);
                    reject(error);
                });
        });
    }

    _addMessage(role, content) {
        const messagesContainer = this.shadowRoot.getElementById('messages');
        const emptyState = this.shadowRoot.getElementById('emptyState');

        // Hide empty state
        if (emptyState) {
            emptyState.style.display = 'none';
        }

        const messageEl = document.createElement('div');
        messageEl.className = `message ${role}`;

        const avatar = role === 'user' ? 'You' : 'AI';

        messageEl.innerHTML = `
      <div class="avatar">${avatar}</div>
      <div class="content">${this._escapeHtml(content)}</div>
    `;

        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        this._messages.push({ role, content });
    }

    _showLoading() {
        const messagesContainer = this.shadowRoot.getElementById('messages');

        const loadingEl = document.createElement('div');
        loadingEl.className = 'message assistant';
        loadingEl.id = 'loadingMessage';
        loadingEl.innerHTML = `
      <div class="avatar">AI</div>
      <div class="loading">
        <div class="loading-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <span>Thinking...</span>
      </div>
    `;

        messagesContainer.appendChild(loadingEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    _hideLoading() {
        const loadingEl = this.shadowRoot.getElementById('loadingMessage');
        if (loadingEl) {
            loadingEl.remove();
        }
    }

    async _newConversation() {
        this._messages = [];

        const messagesContainer = this.shadowRoot.getElementById('messages');
        const emptyState = this.shadowRoot.getElementById('emptyState');

        // Clear messages
        messagesContainer.innerHTML = '';
        messagesContainer.appendChild(emptyState);
        emptyState.style.display = '';

        // Call service
        try {
            await this._hass.callService('chatgpt_plus_ha', 'new_conversation', {});
        } catch (error) {
            console.error('Failed to start new conversation:', error);
        }
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    _generateRequestId() {
        return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }
}

customElements.define('chatgpt-plus-panel', ChatGPTPlusPanel);
