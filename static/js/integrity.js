// ─── Integrity Monitor ───
const IntegrityMonitor = {
  tabSwitches: 0,
  copyPasteCount: 0,
  log: [],
  startTime: Date.now(),
  taskId: null,
  isEnforcing: false,

  getStorageKey() {
    return `codearena_integrity_${this.taskId}`;
  },

  init() {
    this.taskId = document.getElementById('task-id')?.value;
    if (!this.taskId) return;

    // Load existing state
    const saved = sessionStorage.getItem(this.getStorageKey());
    if (saved) {
      try {
        const data = JSON.parse(saved);
        this.tabSwitches = data.tabSwitches || 0;
        this.copyPasteCount = data.copyPasteCount || 0;
        this.log = data.log || [];
        this.updateWarning(); // Restore UI state
      } catch (e) { console.error('Failed to parse integrity state', e); }
    }

    // Tab visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.tabSwitches++;
        this.logEvent('tab_switch', `Tab left (total: ${this.tabSwitches})`);
        this.updateWarning();
        this.saveState();
      }
    });

    // Copy detection
    document.addEventListener('copy', (e) => {
      const sel = window.getSelection()?.toString() || '';
      if (sel.length > 5) {
        this.copyPasteCount++;
        this.logEvent('copy', `Copied ${sel.length} chars`);
        this.updateWarning();
        this.saveState();
      }
    });

    // Paste detection
    document.addEventListener('paste', () => {
      this.copyPasteCount++;
      this.logEvent('paste', 'Paste detected in editor');
      this.updateWarning();
      this.saveState();
    });

    // Right-click
    document.addEventListener('contextmenu', () => {
      this.logEvent('rightclick', 'Right-click menu opened');
      this.saveState();
    });

    // Window blur (switch app)
    window.addEventListener('blur', () => {
      this.logEvent('window_blur', 'Window lost focus');
      this.saveState();
    });
  },

  saveState() {
    if (!this.taskId) return;
    const data = {
      tabSwitches: this.tabSwitches,
      copyPasteCount: this.copyPasteCount,
      log: this.log
    };
    sessionStorage.setItem(this.getStorageKey(), JSON.stringify(data));
  },

  resetState() {
    if (!this.taskId) return;
    sessionStorage.removeItem(this.getStorageKey());
  },

  logEvent(type, detail) {
    this.log.push({
      type, detail,
      time: new Date().toISOString(),
      elapsed: Math.floor((Date.now() - this.startTime) / 1000) + 's'
    });
    this.saveState();
  },

  updateWarning() {
    const bar = document.getElementById('integrity-bar');
    if (!bar) return;
    const flagged = this.tabSwitches > 3 || this.copyPasteCount > 5;
    if (flagged) {
      bar.style.display = 'flex';
      bar.querySelector('#flag-detail').textContent =
        `Tab Switches: ${this.tabSwitches} | Copy/Paste: ${this.copyPasteCount}`;
    }
    // Update counters display
    const tc = document.getElementById('counter-tabs');
    const cp = document.getElementById('counter-paste');
    if (tc) tc.textContent = this.tabSwitches;
    if (cp) cp.textContent = this.copyPasteCount;

    // 🛡️ Enforcement Logic (Auto-submit after 2 switches or 2 copy-pastes)
    if ((this.tabSwitches > 2 || this.copyPasteCount > 2) && !this.isEnforcing) {
      if (typeof submitCode === 'function') {
        this.isEnforcing = true;
        if (typeof showToast === 'function') {
          showToast('🚨 Integrity thresholds exceeded! Auto-submitting work...', 'error');
        }
        setTimeout(() => submitCode(), 1000); // Small delay for toast
      }
    }
  },

  getData() {
    return {
      tab_switches: this.tabSwitches,
      copy_paste_count: this.copyPasteCount,
      integrity_log: this.log,
      time_taken: Math.floor((Date.now() - this.startTime) / 1000)
    };
  }
};

// Auto-init if on editor page
if (document.getElementById('code-editor')) {
  IntegrityMonitor.init();
}
