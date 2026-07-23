chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({
    enabled: true,
    showArrows: true,
    showPanel: true,
    autoAnalyze: true,
    depth: 5
  });
});
