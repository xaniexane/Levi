/* LEVI Automation Bridge — background service worker.
 *
 * Connects to the native host `com.levi.automation` (chrome_host.py) and
 * fires LEVI workflows: on toolbar-button click (fires the configured
 * default flow) and via a context-menu item (fires with the page URL as
 * payload data). Results surface as a Chrome notification.
 */

const HOST = "com.levi.automation";

let port = null;

function connectHost() {
  if (port) return port;
  port = chrome.runtime.connectNative(HOST);
  port.onMessage.addListener((response) => {
    void chrome.notifications.create({
      type: "basic",
      title: "LEVI Automation",
      message: formatResult(response),
    });
    void chrome.storage.local.set({ leviLastResult: response });
    port = null;
  });
  port.onDisconnect.addListener(() => {
    const err = chrome.runtime.lastError
      ? chrome.runtime.lastError.message
      : "host disconnected";
    void chrome.storage.local.set({
      leviLastResult: { ok: false, error: err },
    });
    port = null;
  });
  return port;
}

function formatResult(response) {
  if (!response) return "no response from host";
  if (response.ok) return "workflow fired: " + JSON.stringify(response.results ?? "ok");
  return "failed: " + (response.error ?? "unknown error");
}

function fireWorkflow(flowId, trigger, payload) {
  const msg = { type: "fire-workflow", flow_id: flowId };
  if (trigger) msg.trigger = trigger;
  if (payload) msg.payload = payload; // data only, never instructions
  connectHost().postMessage(msg);
}

chrome.action.onClicked.addListener(async () => {
  const { leviDefaultFlow } = await chrome.storage.local.get("leviDefaultFlow");
  fireWorkflow(leviDefaultFlow || "default", { source: "toolbar" }, {});
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "levi-fire-workflow",
    title: "Fire LEVI workflow with this page",
    contexts: ["page", "selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "levi-fire-workflow") return;
  const { leviDefaultFlow } = await chrome.storage.local.get("leviDefaultFlow");
  fireWorkflow(
    leviDefaultFlow || "default",
    { source: "context-menu" },
    { url: tab ? tab.url : null, selection: info.selectionText || null }
  );
});
