/*
 * Ticketsystem – Lovelace Custom Cards
 * -------------------------------------------------
 * Stellt zwei Karten bereit:
 *   - custom:ticket-submit-card  (Formular zum Einreichen)
 *   - custom:ticket-list-card    (Verwaltung mit Filter, Sortierung, Aktionen)
 *
 * Die Datei wird von der Integration automatisch als JS-Modul geladen.
 * Sie benötigt keinen Build-Schritt und kein externes Framework.
 */

(() => {
  "use strict";

  if (customElements.get("ticket-submit-card")) {
    return; // bereits geladen
  }

  const VERSION = "1.1.5";
  const DOMAIN = "ticket_system";

  const PRIORITIES = ["low", "medium", "high", "critical"];
  const STATUSES = ["open", "in_progress", "closed"];

  const PRIORITY_LABEL = {
    low: "Niedrig",
    medium: "Mittel",
    high: "Hoch",
    critical: "Kritisch",
  };

  const STATUS_LABEL = {
    open: "Offen",
    in_progress: "In Bearbeitung",
    closed: "Abgeschlossen",
  };

  const PRIORITY_RANK = { critical: 4, high: 3, medium: 2, low: 1 };
  const PRIORITY_CLASS = {
    low: "p-low",
    medium: "p-medium",
    high: "p-high",
    critical: "p-critical",
  };
  const STATUS_CLASS = {
    open: "s-open",
    in_progress: "s-progress",
    closed: "s-closed",
  };

  const SUBMIT_DEFAULTS = {
    title: "Ticket einreichen",
    subtitle: "",
    default_priority: "medium",
    allow_author: true,
    show_priority: true,
    show_description: true,
    show_notify: true,
    notify_default: true,
    notify_label: "Team über dieses Ticket benachrichtigen",
    button_label: "Ticket absenden",
    success_message: "Ticket wurde erstellt – vielen Dank!",
  };

  const LIST_DEFAULTS = {
    title: "Ticket-Verwaltung",
    subtitle: "",
    show_closed: true,
    show_description: true,
    allow_status_change: true,
    allow_notify: true,
    allow_delete: true,
    default_status_filter: "all",
    max_items: 0,
  };

  /* ------------------------------------------------------------------ */
  /* Hilfsfunktionen                                                     */
  /* ------------------------------------------------------------------ */

  const esc = (value) =>
    String(value === undefined || value === null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const localeOf = (hass) =>
    (hass && hass.locale && hass.locale.language) ||
    document.documentElement.lang ||
    "de-DE";

  function fmtDate(iso, locale) {
    if (!iso) return "–";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso);
    try {
      return new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
    } catch (err) {
      return date.toLocaleString();
    }
  }

  function fmtRelative(iso, locale) {
    if (!iso) return "–";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso);

    const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
    const absolute = Math.abs(diffSeconds);
    const units = [
      ["year", 31536000],
      ["month", 2592000],
      ["week", 604800],
      ["day", 86400],
      ["hour", 3600],
      ["minute", 60],
    ];

    try {
      const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
      for (const [unit, seconds] of units) {
        if (absolute >= seconds) {
          return rtf.format(Math.round(diffSeconds / seconds), unit);
        }
      }
      return rtf.format(diffSeconds, "second");
    } catch (err) {
      return fmtDate(iso, locale);
    }
  }

  const dateValue = (value) => {
    const time = Date.parse(value || "");
    return Number.isNaN(time) ? 0 : time;
  };

  const buttonDisabled = (busy) => (busy ? "disabled" : "");

  /* ------------------------------------------------------------------ */
  /* Styles                                                              */
  /* ------------------------------------------------------------------ */

  const STYLES = `
    :host { display: block; }
    * { box-sizing: border-box; }

    .card {
      background: var(--ha-card-background, var(--card-background-color, var(--primary-background-color, #fff)));
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12)));
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, none);
      color: var(--primary-text-color);
      padding: 16px;
      height: 100%;
    }

    .card-header {
      align-items: flex-start;
      display: flex;
      gap: 12px;
      justify-content: space-between;
      margin-bottom: 14px;
    }

    .title {
      font-size: var(--ha-card-header-font-size, 20px);
      font-weight: 500;
      line-height: 1.25;
    }

    .subtitle {
      color: var(--secondary-text-color);
      font-size: 13px;
      margin-top: 2px;
    }

    .stats {
      color: var(--secondary-text-color);
      display: flex;
      flex-wrap: wrap;
      font-size: 12px;
      gap: 14px;
      margin-bottom: 12px;
    }

    .stats b { color: var(--primary-text-color); }

    .form { display: flex; flex-direction: column; gap: 12px; }

    .row { display: flex; flex-wrap: wrap; gap: 12px; }
    .row > .field { flex: 1 1 160px; }

    .field { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
    .label { color: var(--secondary-text-color); font-size: 13px; }
    .label .required { color: var(--error-color, #db4437); }

    .input {
      background: var(--secondary-background-color, rgba(0, 0, 0, 0.045));
      border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.2));
      border-radius: 8px;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 14px;
      outline: none;
      padding: 9px 10px;
      width: 100%;
    }

    .input:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 0 1px var(--primary-color);
    }

    textarea.input { min-height: 86px; resize: vertical; }
    select.input { cursor: pointer; }

    .check {
      align-items: center;
      color: var(--secondary-text-color);
      cursor: pointer;
      display: flex;
      font-size: 13px;
      gap: 8px;
    }
    .check input { accent-color: var(--primary-color); height: 18px; width: 18px; }

    .actions { display: flex; flex-wrap: wrap; gap: 8px; }

    .btn {
      background: transparent;
      border: 1px solid transparent;
      border-radius: 8px;
      color: var(--primary-text-color);
      cursor: pointer;
      font: inherit;
      font-size: 14px;
      font-weight: 500;
      padding: 9px 16px;
      transition: background 0.15s ease, filter 0.15s ease;
    }

    .btn:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    .btn:disabled { cursor: default; opacity: 0.45; }

    .btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .btn.primary:hover:not(:disabled) { filter: brightness(1.08); }

    .btn.ghost { border-color: var(--divider-color, rgba(0, 0, 0, 0.2)); color: var(--primary-color); }
    .btn.ghost:hover:not(:disabled) { background: var(--secondary-background-color, rgba(0, 0, 0, 0.05)); }

    .btn.danger { border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
    .btn.danger:hover:not(:disabled) { background: rgba(219, 68, 55, 0.12); }

    .btn.small { border-radius: 7px; font-size: 12.5px; padding: 6px 11px; }

    .msg {
      border-radius: 8px;
      display: none;
      font-size: 13px;
      padding: 9px 11px;
    }
    .msg.show { display: block; }
    .msg.success { background: rgba(67, 160, 71, 0.14); color: var(--success-color, #43a047); }
    .msg.error { background: rgba(219, 68, 55, 0.14); color: var(--error-color, #db4437); }
    .msg.info { background: var(--secondary-background-color, rgba(0, 0, 0, 0.05)); color: var(--secondary-text-color); }

    .toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .toolbar > * { flex: 1 1 132px; }
    .toolbar > .search { flex: 2 1 190px; }

    .list { display: flex; flex-direction: column; gap: 10px; }

    .ticket {
      border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      border-radius: 10px;
      padding: 12px;
    }
    .ticket.is-closed { opacity: 0.68; }

    .ticket-top { display: flex; gap: 10px; justify-content: space-between; }
    .ticket-title { font-size: 15px; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }

    .badges { display: flex; flex-shrink: 0; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }

    .badge {
      border-radius: 999px;
      font-size: 10.5px;
      font-weight: 600;
      letter-spacing: 0.03em;
      padding: 2px 8px;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .p-low { background: rgba(67, 160, 71, 0.16); color: #43a047; }
    .p-medium { background: rgba(30, 136, 229, 0.16); color: #1e88e5; }
    .p-high { background: rgba(251, 140, 0, 0.18); color: #ef6c00; }
    .p-critical { background: rgba(229, 57, 53, 0.18); color: #e53935; }

    .s-open { background: rgba(30, 136, 229, 0.14); color: #1e88e5; }
    .s-progress { background: rgba(251, 140, 0, 0.18); color: #ef6c00; }
    .s-closed { background: rgba(117, 117, 117, 0.18); color: var(--secondary-text-color); }

    .ticket-desc {
      color: var(--secondary-text-color);
      font-size: 13px;
      margin-top: 6px;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }

    .ticket-meta {
      color: var(--secondary-text-color);
      display: flex;
      flex-wrap: wrap;
      font-size: 12px;
      gap: 12px;
      margin-top: 8px;
    }

    .ticket-id { font-family: var(--code-font-family, monospace); opacity: 0.75; }

    .ticket-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }

    .empty {
      color: var(--secondary-text-color);
      font-size: 13px;
      padding: 18px 4px;
      text-align: center;
    }

    .hint {
      border: 1px dashed var(--divider-color, rgba(0, 0, 0, 0.2));
      border-radius: 10px;
      color: var(--secondary-text-color);
      font-size: 13px;
      padding: 14px;
    }
    .hint.error { border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
    .hint code { font-family: var(--code-font-family, monospace); }
  `;

  const EDITOR_STYLES = `
    :host { display: block; }
    * { box-sizing: border-box; }
    .editor { display: flex; flex-direction: column; gap: 12px; padding: 8px 4px; }
    .row { color: var(--primary-text-color); display: flex; flex-direction: column; font-size: 14px; gap: 4px; }
    .row input[type="text"],
    .row input[type="number"],
    .row select {
      background: var(--card-background-color, rgba(0, 0, 0, 0.04));
      border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.2));
      border-radius: 6px;
      color: var(--primary-text-color);
      font: inherit;
      padding: 8px;
      width: 100%;
    }
    .check { align-items: center; flex-direction: row; gap: 8px; }
    .check input { height: 18px; width: 18px; }
  `;

  /* ------------------------------------------------------------------ */
  /* Basisklasse                                                         */
  /* ------------------------------------------------------------------ */

  class TicketCardBase extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = null;
      this._hass = null;
      this._tickets = [];
      this._unsub = null;
      this._token = 0;
      this._built = false;
      this._error = "";
    }

    /* -- Lovelace API ------------------------------------------------- */

    get hass() {
      return this._hass;
    }

    set hass(hass) {
      const firstHass = !this._hass;
      this._hass = hass;
      if (!this._config) return;

      if (firstHass) {
        this._build();
        this._connect();
      } else {
        this._onHassUpdate();
      }
    }

    setConfig(config) {
      const merged = Object.assign({}, this._cardDefaults(), config || {});
      this._config = merged;
      this._build();
      this._afterConfig();
    }

    connectedCallback() {
      if (this._config && !this._built) this._build();
      if (this._hass) this._connect();
    }

    disconnectedCallback() {
      this._disconnect();
    }

    getCardSize() {
      return 4;
    }

    /* -- Überschreibbare Hooks ---------------------------------------- */

    _cardDefaults() {
      return {};
    }

    _build() {}

    _afterConfig() {}

    _onHassUpdate() {}

    _connect() {}

    _disconnect() {
      this._token += 1;
      if (typeof this._unsub === "function") {
        try {
          this._unsub();
        } catch (err) {
          /* Verbindung ggf. schon geschlossen */
        }
      }
      this._unsub = null;
    }

    /* -- Helfer -------------------------------------------------------- */

    _field(name) {
      return this.shadowRoot
        ? this.shadowRoot.querySelector(`[name="${name}"]`)
        : null;
    }

    _value(name) {
      const field = this._field(name);
      return field ? String(field.value || "") : "";
    }
  }

  /* ------------------------------------------------------------------ */
  /* Karte: Ticket einreichen                                            */
  /* ------------------------------------------------------------------ */

  class TicketSubmitCard extends TicketCardBase {
    constructor() {
      super();
      this._busy = false;
    }

    _cardDefaults() {
      return Object.assign({}, SUBMIT_DEFAULTS);
    }

    getCardSize() {
      return 6;
    }

    _defaultAuthor() {
      return (this._hass && this._hass.user && this._hass.user.name) || "";
    }

    _build() {
      const config = this._config;
      if (!config) return;

      const priorityOptions = PRIORITIES.map(
        (value) =>
          `<option value="${value}"${
            value === config.default_priority ? " selected" : ""
          }>${esc(PRIORITY_LABEL[value])}</option>`
      ).join("");

      this.shadowRoot.innerHTML = `
        <style>${STYLES}</style>
        <div class="card">
          <div class="card-header">
            <div>
              <div class="title">${esc(config.title)}</div>
              ${config.subtitle ? `<div class="subtitle">${esc(config.subtitle)}</div>` : ""}
            </div>
          </div>

          <form class="form" novalidate>
            <label class="field">
              <span class="label">Titel <span class="required">*</span></span>
              <input class="input" name="title" type="text" maxlength="200"
                     autocomplete="off" placeholder="Kurze Zusammenfassung des Problems">
            </label>

            ${
              config.show_description
                ? `<label class="field">
                     <span class="label">Beschreibung</span>
                     <textarea class="input" name="description" rows="4"
                               placeholder="Was ist passiert? Wo? Seit wann?"></textarea>
                   </label>`
                : ""
            }

            <div class="row">
              ${
                config.show_priority
                  ? `<label class="field">
                       <span class="label">Dringlichkeit</span>
                       <select class="input" name="priority">${priorityOptions}</select>
                     </label>`
                  : ""
              }

              ${
                config.allow_author
                  ? `<label class="field">
                       <span class="label">Ersteller</span>
                       <input class="input" name="author" type="text" maxlength="100"
                              autocomplete="name" value="${esc(this._defaultAuthor())}">
                     </label>`
                  : ""
              }
            </div>

            ${
              config.show_notify
                ? `<label class="check">
                     <input type="checkbox" name="notify"${
                       config.notify_default ? " checked" : ""
                     }>
                     <span>${esc(config.notify_label)}</span>
                   </label>`
                : ""
            }

            <div class="actions">
              <button class="btn primary" type="submit">${esc(config.button_label)}</button>
              <button class="btn ghost" type="reset">Zurücksetzen</button>
            </div>

            <div class="msg" role="status" aria-live="polite"></div>
          </form>
        </div>
      `;

      this._form = this.shadowRoot.querySelector("form");
      this._msg = this.shadowRoot.querySelector(".msg");
      this._form.addEventListener("submit", (event) => this._submit(event));
      this._form.addEventListener("reset", () => {
        window.setTimeout(() => {
          this._resetFields();
          this._showMessage();
        }, 0);
      });

      this._built = true;
    }

    _resetFields() {
      const title = this._field("title");
      if (title) title.value = "";
      const description = this._field("description");
      if (description) description.value = "";
      const author = this._field("author");
      if (author) author.value = this._defaultAuthor();
      const priority = this._field("priority");
      if (priority) priority.value = this._config.default_priority || "medium";
      const notify = this._field("notify");
      if (notify) notify.checked = Boolean(this._config.notify_default);
    }

    _showMessage(kind, text) {
      if (!this._msg) return;
      if (!kind || !text) {
        this._msg.className = "msg";
        this._msg.textContent = "";
        return;
      }
      this._msg.className = `msg show ${kind}`;
      this._msg.textContent = text;
    }

    _setBusy(busy) {
      const button = this.shadowRoot.querySelector("button[type='submit']");
      if (button) {
        button.disabled = busy;
        button.textContent = busy ? "Wird gesendet …" : this._config.button_label;
      }
    }

    async _submit(event) {
      event.preventDefault();
      if (!this._hass || this._busy) return;

      const title = this._value("title").trim();
      const description = this._value("description").trim();
      const priority = this._value("priority") || "medium";
      const author = (this._value("author") || this._defaultAuthor()).trim();
      const notifyField = this._field("notify");
      const notify = notifyField
        ? Boolean(notifyField.checked)
        : Boolean(this._config.show_notify ? this._config.notify_default : true);

      if (!title) {
        this._showMessage("error", "Bitte gib einen Titel für das Ticket ein.");
        const titleField = this._field("title");
        if (titleField) titleField.focus();
        return;
      }

      this._busy = true;
      this._setBusy(true);
      this._showMessage("info", "Ticket wird gesendet …");

      try {
        await this._hass.callService(
          DOMAIN,
          "create",
          {
            title,
            description,
            priority,
            status: "open",
            author: author || "Unbekannt",
            notify,
          },
          undefined,
          false
        );

        this._resetFields();
        this._showMessage("success", this._config.success_message);

        this.dispatchEvent(
          new CustomEvent("ticket-created", {
            detail: { title, priority },
            bubbles: true,
            composed: true,
          })
        );
      } catch (err) {
        const message = err && err.message ? err.message : String(err);
        this._showMessage(
          "error",
          `Ticket konnte nicht erstellt werden: ${message}`
        );
      } finally {
        this._busy = false;
        this._setBusy(false);
      }
    }

    static getStubConfig() {
      return {};
    }

    getConfigElement() {
      return document.createElement("ticket-submit-card-editor");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Karte: Ticket-Verwaltung                                            */
  /* ------------------------------------------------------------------ */

  class TicketListCard extends TicketCardBase {
    constructor() {
      super();
      this._filterStatus = "all";
      this._filterPriority = "all";
      this._search = "";
      this._sort = "priority";
      this._busyIds = new Set();
      this._loaded = false;
      this._toast = null;
    }

    _cardDefaults() {
      return Object.assign({}, LIST_DEFAULTS);
    }

    getCardSize() {
      return 8;
    }

    /* -- Verbindung ---------------------------------------------------- */

    async _connect() {
      if (!this._hass || !this._hass.connection || this._unsub) return;

      const token = ++this._token;
      try {
        const unsub = await this._hass.connection.subscribeMessage(
          (message) =>
            this._setTickets((message && message.tickets) || []),
          { type: `${DOMAIN}/subscribe` }
        );

        if (token !== this._token) {
          try {
            unsub();
          } catch (err) {
            /* ignore */
          }
          return;
        }

        this._unsub = unsub;
        this._error = "";
        this._renderList();
      } catch (err) {
        if (token !== this._token) return;
        this._error = err && err.message ? err.message : String(err);
        this._renderList();
      }
    }

    _onHassUpdate() {
      if (this._error && !this._unsub) this._connect();
    }

    /* -- Aufbau -------------------------------------------------------- */

    _build() {
      const config = this._config;
      if (!config) return;

      const initialFilter = config.default_status_filter || "all";
      this._filterStatus =
        initialFilter === "all" || STATUSES.includes(initialFilter)
          ? initialFilter
          : "all";

      const statusOptions = [["all", "Alle Status"]]
        .concat(STATUSES.map((status) => [status, STATUS_LABEL[status]]))
        .map(
          ([value, label]) =>
            `<option value="${value}"${
              value === this._filterStatus ? " selected" : ""
            }>${esc(label)}</option>`
        )
        .join("");

      const priorityOptions = [["all", "Alle Dringlichkeiten"]]
        .concat(PRIORITIES.slice().reverse().map((value) => [value, PRIORITY_LABEL[value]]))
        .map(
          ([value, label]) =>
            `<option value="${value}">${esc(label)}</option>`
        )
        .join("");

      const sortOptions = [
        ["priority", "Dringlichkeit"],
        ["newest", "Neueste zuerst"],
        ["oldest", "Älteste zuerst"],
        ["updated", "Zuletzt geändert"],
      ]
        .map(
          ([value, label]) =>
            `<option value="${value}"${
              value === this._sort ? " selected" : ""
            }>${esc(label)}</option>`
        )
        .join("");

      this.shadowRoot.innerHTML = `
        <style>${STYLES}</style>
        <div class="card">
          <div class="card-header">
            <div>
              <div class="title">${esc(config.title)}</div>
              ${config.subtitle ? `<div class="subtitle">${esc(config.subtitle)}</div>` : ""}
            </div>
            <span class="badge count-badge"></span>
          </div>

          <div class="stats"></div>

          <div class="toolbar">
            <input class="input search" type="search" placeholder="Suchen (Titel, Text, Ersteller)"
                   value="${esc(this._search)}" aria-label="Tickets durchsuchen">
            <select class="input filter-status" aria-label="Nach Status filtern">${statusOptions}</select>
            <select class="input filter-priority" aria-label="Nach Dringlichkeit filtern">${priorityOptions}</select>
            <select class="input sorter" aria-label="Sortierung">${sortOptions}</select>
          </div>

          <div class="msg" role="status" aria-live="polite"></div>
          <div class="list"></div>
          <div class="empty" style="display:none"></div>
        </div>
      `;

      this._listEl = this.shadowRoot.querySelector(".list");
      this._emptyEl = this.shadowRoot.querySelector(".empty");
      this._statsEl = this.shadowRoot.querySelector(".stats");
      this._countEl = this.shadowRoot.querySelector(".count-badge");
      this._toastEl = this.shadowRoot.querySelector(".msg");

      const search = this.shadowRoot.querySelector(".search");
      search.addEventListener("input", () => {
        this._search = search.value;
        this._renderList();
      });

      const status = this.shadowRoot.querySelector(".filter-status");
      status.addEventListener("change", () => {
        this._filterStatus = status.value;
        this._renderList();
      });

      const priority = this.shadowRoot.querySelector(".filter-priority");
      priority.addEventListener("change", () => {
        this._filterPriority = priority.value;
        this._renderList();
      });

      const sorter = this.shadowRoot.querySelector(".sorter");
      sorter.addEventListener("change", () => {
        this._sort = sorter.value;
        this._renderList();
      });

      this._listEl.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-action]");
        if (!trigger) return;
        event.preventDefault();
        this._handleAction(trigger.dataset.action, trigger.dataset.id);
      });

      this._renderList();
      this._built = true;
    }

    /* -- Daten --------------------------------------------------------- */

    _setTickets(tickets) {
      this._tickets = Array.isArray(tickets) ? tickets : [];
      this._loaded = true;
      this._renderList();
    }

    _visibleTickets() {
      const config = this._config || LIST_DEFAULTS;
      let list = Array.isArray(this._tickets) ? this._tickets.slice() : [];

      if (!config.show_closed) {
        list = list.filter((ticket) => ticket.status !== "closed");
      }
      if (this._filterStatus !== "all") {
        list = list.filter((ticket) => ticket.status === this._filterStatus);
      }
      if (this._filterPriority !== "all") {
        list = list.filter((ticket) => ticket.priority === this._filterPriority);
      }

      const query = this._search.trim().toLowerCase();
      if (query) {
        list = list.filter((ticket) =>
          [ticket.title, ticket.description, ticket.author, ticket.id]
            .join(" ")
            .toLowerCase()
            .includes(query)
        );
      }

      const sorters = {
        priority: (a, b) =>
          (PRIORITY_RANK[b.priority] || 0) - (PRIORITY_RANK[a.priority] || 0) ||
          dateValue(b.created_at) - dateValue(a.created_at),
        newest: (a, b) => dateValue(b.created_at) - dateValue(a.created_at),
        oldest: (a, b) => dateValue(a.created_at) - dateValue(b.created_at),
        updated: (a, b) =>
          dateValue(b.updated_at || b.created_at) -
          dateValue(a.updated_at || a.created_at),
      };

      list.sort(sorters[this._sort] || sorters.priority);

      const maxItems = Number(config.max_items) || 0;
      if (maxItems > 0) list = list.slice(0, maxItems);
      return list;
    }

    /* -- Darstellung --------------------------------------------------- */

    _renderList() {
      if (!this._listEl) return;

      const all = Array.isArray(this._tickets) ? this._tickets : [];
      const visible = this._visibleTickets();

      if (this._statsEl) {
        const open = all.filter((ticket) => ticket.status === "open").length;
        const progress = all.filter(
          (ticket) => ticket.status === "in_progress"
        ).length;
        const closed = all.filter((ticket) => ticket.status === "closed").length;
        this._statsEl.innerHTML = `
          <span class="stat"><b>${open}</b> offen</span>
          <span class="stat"><b>${progress}</b> in Bearbeitung</span>
          <span class="stat"><b>${closed}</b> abgeschlossen</span>
        `;
      }

      if (this._countEl) {
        const active = all.filter((ticket) => ticket.status !== "closed").length;
        this._countEl.className = "badge count-badge s-open";
        this._countEl.textContent = `${active} aktiv`;
      }

      if (this._error) {
        this._listEl.innerHTML = `
          <div class="hint error">
            Tickets konnten nicht geladen werden: ${esc(this._error)}<br>
            <small>Ist die Integration <code>ticket_system</code> eingerichtet und geladen?</small>
          </div>
        `;
        if (this._emptyEl) this._emptyEl.style.display = "none";
        return;
      }

      if (!visible.length) {
        this._listEl.innerHTML = "";
        if (this._emptyEl) {
          this._emptyEl.style.display = "block";
          if (!this._loaded) {
            this._emptyEl.textContent = "Tickets werden geladen …";
          } else if (all.length) {
            this._emptyEl.textContent = "Keine Tickets für diesen Filter.";
          } else {
            this._emptyEl.textContent = "Noch keine Tickets vorhanden.";
          }
        }
        return;
      }

      if (this._emptyEl) this._emptyEl.style.display = "none";
      this._listEl.innerHTML = visible
        .map((ticket) => this._ticketHtml(ticket))
        .join("");
    }

    _ticketHtml(ticket) {
      const config = this._config || LIST_DEFAULTS;
      const locale = localeOf(this._hass);
      const status = ticket.status || "open";
      const priority = ticket.priority || "medium";
      const busy = this._busyIds.has(ticket.id);

      const actions = [];

      if (config.allow_status_change && status === "open") {
        actions.push(
          `<button class="btn small ghost" data-action="progress" data-id="${esc(
            ticket.id
          )}" ${buttonDisabled(busy)}>In Bearbeitung</button>`
        );
      }
      if (config.allow_status_change && status !== "closed") {
        actions.push(
          `<button class="btn small primary" data-action="close" data-id="${esc(
            ticket.id
          )}" ${buttonDisabled(busy)}>Abschließen</button>`
        );
      }
      if (config.allow_status_change && status === "closed") {
        actions.push(
          `<button class="btn small ghost" data-action="reopen" data-id="${esc(
            ticket.id
          )}" ${buttonDisabled(busy)}>Wieder öffnen</button>`
        );
      }
      if (config.allow_notify) {
        actions.push(
          `<button class="btn small ghost" data-action="notify" data-id="${esc(
            ticket.id
          )}" ${buttonDisabled(busy)}>Benachrichtigen</button>`
        );
        if (status !== "closed") {
          actions.push(
            `<button class="btn small ghost" data-action="remind" data-id="${esc(
              ticket.id
            )}" ${buttonDisabled(busy)}>Erinnerung</button>`
          );
        }
      }
      if (config.allow_delete) {
        actions.push(
          `<button class="btn small danger" data-action="delete" data-id="${esc(
            ticket.id
          )}" ${buttonDisabled(busy)}>Löschen</button>`
        );
      }

      return `
        <div class="ticket${status === "closed" ? " is-closed" : ""}">
          <div class="ticket-top">
            <div class="ticket-title">${esc(ticket.title || "(ohne Titel)")}</div>
            <div class="badges">
              <span class="badge ${PRIORITY_CLASS[priority] || ""}">${esc(
        PRIORITY_LABEL[priority] || priority
      )}</span>
              <span class="badge ${STATUS_CLASS[status] || ""}">${esc(
        STATUS_LABEL[status] || status
      )}</span>
            </div>
          </div>
          ${
            config.show_description && ticket.description
              ? `<div class="ticket-desc">${esc(ticket.description)}</div>`
              : ""
          }
          <div class="ticket-meta">
            <span title="${esc(fmtDate(ticket.created_at, locale))}">🕒 ${esc(
        fmtRelative(ticket.created_at, locale)
      )}</span>
            <span>👤 ${esc(ticket.author || "Unbekannt")}</span>
            <span class="ticket-id">#${esc(ticket.id || "")}</span>
          </div>
          ${actions.length ? `<div class="ticket-actions">${actions.join("")}</div>` : ""}
        </div>
      `;
    }

    _showToast(kind, text) {
      this._toast = text ? { kind, text } : null;
      if (!this._toastEl) return;
      if (!this._toast) {
        this._toastEl.className = "msg";
        this._toastEl.textContent = "";
        return;
      }
      this._toastEl.className = `msg show ${this._toast.kind}`;
      this._toastEl.textContent = this._toast.text;
    }

    /* -- Aktionen ------------------------------------------------------ */

    async _handleAction(action, id) {
      if (!this._hass || !id || this._busyIds.has(id)) return;

      if (action === "delete") {
        const ticket = this._tickets.find((item) => item.id === id);
        const label = ticket && ticket.title ? `„${ticket.title}“` : `#${id}`;
        if (!window.confirm(`Ticket ${label} wirklich löschen?`)) return;
      }

      const statusByAction = {
        progress: "in_progress",
        close: "closed",
        reopen: "open",
      };

      this._busyIds.add(id);
      this._renderList();
      this._showToast();

      try {
        if (action === "delete") {
          await this._hass.callService(DOMAIN, "delete", { ticket_id: id });
          this._tickets = this._tickets.filter((ticket) => ticket.id !== id);
        } else if (statusByAction[action]) {
          const status = statusByAction[action];
          await this._hass.callService(DOMAIN, "set_status", {
            ticket_id: id,
            status,
          });
          this._tickets = this._tickets.map((ticket) =>
            ticket.id === id
              ? Object.assign({}, ticket, {
                  status,
                  updated_at: new Date().toISOString(),
                })
              : ticket
          );
        } else if (action === "notify" || action === "remind") {
          const response = await this._hass.callService(
            DOMAIN,
            "notify",
            {
              ticket_id: id,
              kind: action === "remind" ? "reminder" : "info",
            },
            undefined,
            true
          );
          const sent = (response && response.sent) || [];
          this._showToast(
            "success",
            sent.length
              ? `Benachrichtigung gesendet (${sent.join(", ")}).`
              : "Benachrichtigung gesendet."
          );
        }
      } catch (err) {
        const message = err && err.message ? err.message : String(err);
        this._showToast("error", `Aktion fehlgeschlagen: ${message}`);
      } finally {
        this._busyIds.delete(id);
        this._renderList();
      }
    }

    static getStubConfig() {
      return {};
    }

    getConfigElement() {
      return document.createElement("ticket-list-card-editor");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Editoren                                                            */
  /* ------------------------------------------------------------------ */

  class TicketBaseEditor extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
      this._rendered = false;
    }

    set hass(hass) {
      this._hass = hass;
    }

    setConfig(config) {
      this._config = Object.assign({}, this._editorDefaults(), config || {});
      if (!this._rendered) {
        this._render();
        this._rendered = true;
      } else {
        this._sync();
      }
    }

    _editorDefaults() {
      return {};
    }

    _fields() {
      return [];
    }

    _render() {
      const fields = this._fields();
      this.shadowRoot.innerHTML = `
        <style>${EDITOR_STYLES}</style>
        <div class="editor">
          ${fields.map((field) => this._fieldHtml(field)).join("")}
        </div>
      `;
      fields.forEach((field) => this._bindField(field));
    }

    _fieldHtml(field) {
      const value = this._config[field.key];

      if (field.type === "boolean") {
        return `
          <label class="row check">
            <input type="checkbox" data-key="${field.key}" ${value ? "checked" : ""}>
            <span>${esc(field.label)}</span>
          </label>
        `;
      }

      if (field.type === "select") {
        const options = (field.options || [])
          .map(
            (option) =>
              `<option value="${esc(option.value)}"${
                String(value) === String(option.value) ? " selected" : ""
              }>${esc(option.label)}</option>`
          )
          .join("");
        return `
          <label class="row">
            <span>${esc(field.label)}</span>
            <select data-key="${field.key}">${options}</select>
          </label>
        `;
      }

      return `
        <label class="row">
          <span>${esc(field.label)}</span>
          <input type="${field.type === "number" ? "number" : "text"}"
                 data-key="${field.key}"
                 value="${esc(value === undefined || value === null ? "" : value)}"
                 placeholder="${esc(field.placeholder || "")}"
                 ${field.type === "number" ? 'min="0" step="1"' : ""}>
        </label>
      `;
    }

    _bindField(field) {
      const element = this.shadowRoot.querySelector(
        `[data-key="${field.key}"]`
      );
      if (!element) return;

      element.addEventListener("change", () => {
        let value;
        if (field.type === "boolean") {
          value = element.checked;
        } else if (field.type === "number") {
          value = element.value === "" ? undefined : Number(element.value);
        } else {
          value = element.value;
        }

        const config = Object.assign({}, this._config);
        if (value === undefined || value === "") {
          delete config[field.key];
        } else {
          config[field.key] = value;
        }
        this._config = config;

        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config },
            bubbles: true,
            composed: true,
          })
        );
      });
    }

    _sync() {
      this._fields().forEach((field) => {
        const element = this.shadowRoot.querySelector(
          `[data-key="${field.key}"]`
        );
        if (!element) return;
        const value = this._config[field.key];

        if (field.type === "boolean") {
          element.checked = Boolean(value);
        } else if (String(element.value) !== String(value === undefined ? "" : value)) {
          element.value = value === undefined ? "" : value;
        }
      });
    }
  }

  class TicketSubmitCardEditor extends TicketBaseEditor {
    _editorDefaults() {
      return SUBMIT_DEFAULTS;
    }

    _fields() {
      return [
        { key: "title", label: "Titel", type: "text" },
        { key: "subtitle", label: "Untertitel", type: "text" },
        {
          key: "default_priority",
          label: "Vorausgewählte Dringlichkeit",
          type: "select",
          options: PRIORITIES.map((value) => ({
            value,
            label: PRIORITY_LABEL[value],
          })),
        },
        { key: "show_priority", label: "Dringlichkeit anzeigen", type: "boolean" },
        { key: "show_description", label: "Beschreibung anzeigen", type: "boolean" },
        { key: "allow_author", label: "Ersteller-Feld anzeigen", type: "boolean" },
        {
          key: "show_notify",
          label: "Benachrichtigungs-Auswahl anzeigen",
          type: "boolean",
        },
        {
          key: "notify_default",
          label: "Benachrichtigung standardmäßig aktiv",
          type: "boolean",
        },
        {
          key: "notify_label",
          label: "Text der Benachrichtigungs-Auswahl",
          type: "text",
        },
        { key: "button_label", label: "Beschriftung des Buttons", type: "text" },
        { key: "success_message", label: "Erfolgsmeldung", type: "text" },
      ];
    }
  }

  class TicketListCardEditor extends TicketBaseEditor {
    _editorDefaults() {
      return LIST_DEFAULTS;
    }

    _fields() {
      return [
        { key: "title", label: "Titel", type: "text" },
        { key: "subtitle", label: "Untertitel", type: "text" },
        { key: "show_closed", label: "Abgeschlossene Tickets anzeigen", type: "boolean" },
        { key: "show_description", label: "Beschreibung anzeigen", type: "boolean" },
        { key: "allow_status_change", label: "Statusänderung erlauben", type: "boolean" },
        {
          key: "allow_notify",
          label: "Benachrichtigen/Erinnern erlauben",
          type: "boolean",
        },
        { key: "allow_delete", label: "Löschen erlauben", type: "boolean" },
        {
          key: "default_status_filter",
          label: "Standard-Statusfilter",
          type: "select",
          options: [{ value: "all", label: "Alle Status" }].concat(
            STATUSES.map((value) => ({ value, label: STATUS_LABEL[value] }))
          ),
        },
        {
          key: "max_items",
          label: "Maximale Anzahl Tickets (0 = alle)",
          type: "number",
        },
      ];
    }
  }

  /* ------------------------------------------------------------------ */
  /* Registrierung                                                       */
  /* ------------------------------------------------------------------ */

  const CARD_ELEMENTS = [
    ["ticket-submit-card", TicketSubmitCard],
    ["ticket-list-card", TicketListCard],
    ["ticket-submit-card-editor", TicketSubmitCardEditor],
    ["ticket-list-card-editor", TicketListCardEditor],
  ];

  const defineElements = () => {
    for (const [tag, ctor] of CARD_ELEMENTS) {
      if (customElements.get(tag)) continue;
      try {
        customElements.define(tag, ctor);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(`TICKET-SYSTEM: ${tag} nicht registrierbar`, err);
      }
    }
  };

  defineElements();

  window.customCards = window.customCards || [];
  window.customCards.push(
    {
      type: "ticket-submit-card",
      name: "Ticket einreichen",
      description:
        "Formular zum Einreichen neuer Tickets im lokalen Ticketsystem.",
      preview: true,
    },
    {
      type: "ticket-list-card",
      name: "Ticket-Verwaltung",
      description:
        "Liste aller Tickets mit Filter, Sortierung nach Dringlichkeit und Status-Aktionen.",
      preview: true,
    }
  );

  /*
   * Das Home-Assistant-Frontend ersetzt beim Start window.customElements durch
   * das Polyfill für "scoped custom element registries". Module, die über
   * add_extra_js_url eingebunden werden, laufen häufig vorher – ihre
   * Registrierungen sind danach unsichtbar und die Karte meldet "Custom
   * element doesn't exist" (home-assistant/frontend#53890). Deshalb nach der
   * Übernahme erneut registrieren, bis die Elemente in der neuen Registry
   * stehen.
   */
  const registryAtLoad = window.customElements;
  let recheckTimer = null;
  let recheckCount = 0;

  const syncRegistration = () => {
    defineElements();
    recheckCount += 1;
    const polyfillActive = window.customElements !== registryAtLoad;
    if (polyfillActive || recheckCount >= 24) {
      window.clearInterval(recheckTimer);
      window.removeEventListener("load", syncRegistration);
    }
  };

  recheckTimer = window.setInterval(syncRegistration, 250);
  window.addEventListener("load", syncRegistration);

  // eslint-disable-next-line no-console
  console.info(
    `%c TICKET-SYSTEM %c ${VERSION} geladen `,
    "background:#1e88e5;color:#fff;border-radius:3px 0 0 3px;padding:2px 4px;",
    "background:#333;color:#fff;border-radius:0 3px 3px 0;padding:2px 4px;"
  );
})();
