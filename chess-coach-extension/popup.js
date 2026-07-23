document.addEventListener('DOMContentLoaded', () => {
  const controls = {
    enabled: document.getElementById('enabled'),
    autoAnalyze: document.getElementById('autoAnalyze'),
    showArrows: document.getElementById('showArrows'),
    showPanel: document.getElementById('showPanel'),
    depth: document.getElementById('depth')
  };

  chrome.storage.sync.get({
    enabled: true,
    autoAnalyze: true,
    showArrows: true,
    showPanel: true,
    depth: 5
  }, (settings) => {
    controls.enabled.checked = settings.enabled;
    controls.autoAnalyze.checked = settings.autoAnalyze;
    controls.showArrows.checked = settings.showArrows;
    controls.showPanel.checked = settings.showPanel;
    controls.depth.value = settings.depth;
    updateStatus(settings.enabled);
  });

  for (const [key, el] of Object.entries(controls)) {
    const event = el.tagName === 'SELECT' ? 'change' : 'change';
    el.addEventListener(event, () => {
      const value = el.tagName === 'SELECT' ? parseInt(el.value) : el.checked;
      chrome.storage.sync.set({ [key]: value });
      if (key === 'enabled') updateStatus(value);
    });
  }

  function updateStatus(enabled) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    dot.className = 'status-dot ' + (enabled ? 'active' : 'inactive');
    text.textContent = enabled ? 'Coach is active' : 'Coach is paused';
  }
});
