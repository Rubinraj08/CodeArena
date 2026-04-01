// ─── Integrity Monitor ───
const IntegrityMonitor = {
  tabSwitches: 0,
  copyPasteCount: 0,
  log: [],
  startTime: Date.now(),

  init() {
    // Tab visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.tabSwitches++;
        this.logEvent('tab_switch', `Tab left (total: ${this.tabSwitches})`);
        this.updateWarning();
      }
    });

    // Copy detection
    document.addEventListener('copy', (e) => {
      const sel = window.getSelection()?.toString() || '';
      if (sel.length > 5) {
        this.copyPasteCount++;
        this.logEvent('copy', `Copied ${sel.length} chars`);
        this.updateWarning();
      }
    });

    // Paste detection
    document.addEventListener('paste', () => {
      this.copyPasteCount++;
      this.logEvent('paste', 'Paste detected in editor');
      this.updateWarning();
    });

    // Right-click
    document.addEventListener('contextmenu', () => {
      this.logEvent('rightclick', 'Right-click menu opened');
    });

    // Window blur (switch app)
    window.addEventListener('blur', () => {
      this.logEvent('window_blur', 'Window lost focus');
    });
  },

  logEvent(type, detail) {
    this.log.push({
      type, detail,
      time: new Date().toISOString(),
      elapsed: Math.floor((Date.now() - this.startTime) / 1000) + 's'
    });
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
