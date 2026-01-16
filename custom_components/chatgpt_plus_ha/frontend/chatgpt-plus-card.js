class ChatGPTPlusCard extends HTMLElement {
  setConfig(config) {
    this._config = {
      title: 'GPTforHA',
      summary_ttl: 300,
      actions: [],
      ...config,
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialize();
      this._initialized = true;
    }
    this._refreshSummary(false);
  }

  _initialize() {
    this.innerHTML = `
      <ha-card header="${this._config.title}">
        <div class="card-content">
          <div id="summary" style="white-space: pre-wrap;"></div>
          <div id="suggestions" style="margin-top: 12px;"></div>
          <div id="actions" style="margin-top: 12px;"></div>
          <div id="status" style="margin-top: 10px; color: var(--secondary-text-color); font-size: 12px;"></div>
          <div style="margin-top: 10px;">
            <mwc-button id="refreshBtn" outlined>Refresh Summary</mwc-button>
          </div>
        </div>
      </ha-card>
    `;

    this._summaryEl = this.querySelector('#summary');
    this._suggestionsEl = this.querySelector('#suggestions');
    this._actionsEl = this.querySelector('#actions');
    this._statusEl = this.queryVisible('#status');

    this.querySelector('#refreshBtn').addEventListener('click', () => this._refreshSummary(true));
    this._renderActions();
  }

  queryVisible(selector) {
    return this.querySelector(selector);
  }

  _renderActions() {
    if (!this._actionsEl) return;
    const actions = this._config.actions || [];
    if (!actions.length) {
      this._actionsEl.textContent = '';
      return;
    }

    this._actionsEl.innerHTML = '';
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.flexWrap = 'wrap';
    container.style.gap = '8px';
    actions.forEach((action) => {
      const button = document.createElement('mwc-button');
      const prompt = typeof action === 'string' ? action : action.prompt;
      const label = typeof action === 'string' ? action : action.label || action.prompt;
      button.textContent = label;
      button.outlined = true;
      button.addEventListener('click', () => this._sendQuickAction(prompt));
      container.appendChild(button);
    });
    this._actionsEl.appendChild(container);
  }

  async _sendQuickAction(prompt) {
    if (!prompt) {
      return;
    }
    this._statusEl.textContent = 'Sending...';
    try {
      await this._hass.callService('chatgpt_plus_ha', 'send_message', {
        message: prompt,
      });
      this._statusEl.textContent = 'Sent. Check the chat panel for responses.';
    } catch (error) {
      this._statusEl.textContent = `Failed to send: ${error.message || error}`;
    }
  }

  async _refreshSummary(force) {
    if (!this._hass) return;
    const now = Date.now();
    if (!force && this._lastSummaryAt && now - this._lastSummaryAt < this._config.summary_ttl * 1000) {
      return;
    }
    this._lastSummaryAt = now;
    this._statusEl.textContent = 'Loading summary...';
    try {
      const response = await this._callServiceWithResponse('chatgpt_plus_ha', 'build_context', {
        summary_only: true,
        include_suggestions: true,
      });

      this._summaryEl.textContent = response?.summary || 'No summary available.';
      const suggestions = response?.recent_suggestions || [];
      if (suggestions.length) {
        const list = suggestions
          .slice(0, 3)
          .map((item) => `- ${item.response}`)
          .join('\n');
        this._suggestionsEl.textContent = `Latest suggestions:\n${list}`;
      } else {
        this._suggestionsEl.textContent = 'Latest suggestions: none yet.';
      }
      this._statusEl.textContent = 'Summary updated.';
    } catch (error) {
      this._summaryEl.textContent = 'Failed to load summary.';
      this._statusEl.textContent = error.message || error;
    }
  }

  async _callServiceWithResponse(domain, service, serviceData) {
    const response = await this._hass.connection.sendMessagePromise({
      type: 'call_service',
      domain,
      service,
      service_data: serviceData,
      return_response: true,
    });
    if (response && response.response) {
      const key = `${domain}.${service}`;
      return response.response[key] || response.response;
    }
    return response;
  }

  getCardSize() {
    return 4;
  }
}

customElements.define('chatgpt-plus-card', ChatGPTPlusCard);
