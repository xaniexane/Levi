/* LEVI Automation Bridge — popup.
 *
 * The workflow list is user-configured and stored locally
 * (chrome.storage.local.leviFlows). Each row fires one workflow through
 * the background worker -> native host -> LEVI engine path. The popup
 * polls for the last result and shows it.
 */

const HOST = "com.levi.automation";

const flowsEl = document.getElementById("flows");
const newFlowEl = document.getElementById("newFlow");
const resultEl = document.getElementById("result");

async function getFlows() {
  const { leviFlows } = await chrome.storage.local.get("leviFlows");
  return Array.isArray(leviFlows) && leviFlows.length ? leviFlows : ["default"];
}

async function setFlows(flows) {
  await chrome.storage.local.set({ leviFlows: flows });
}

function fire(flowId) {
  const port = chrome.runtime.connectNative(HOST);
  port.onMessage.addListener((response) => {
    void chrome.storage.local.set({ leviLastResult: response });
    port.disconnect();
  });
  port.onDisconnect.addListener(() => {
    port.disconnect();
  });
  port.postMessage({ type: "fire-workflow", flow_id: flowId });
}

async function render() {
  const flows = await getFlows();
  flowsEl.innerHTML = "";
  flows.forEach((flowId, i) => {
    const row = document.createElement("div");
    row.className = "flow";
    const label = document.createElement("input");
    label.value = flowId;
    label.readOnly = true;
    const fireBtn = document.createElement("button");
    fireBtn.textContent = "Fire";
    fireBtn.onclick = () => fire(flowId);
    const defBtn = document.createElement("button");
    defBtn.textContent = "Default";
    defBtn.title = "Set as toolbar-click default";
    defBtn.onclick = () => chrome.storage.local.set({ leviDefaultFlow: flowId });
    const delBtn = document.createElement("button");
    delBtn.textContent = "✕";
    delBtn.onclick = async () => {
      flows.splice(i, 1);
      await setFlows(flows.length ? flows : ["default"]);
      void render();
    };
    row.append(label, fireBtn, defBtn, delBtn);
    flowsEl.appendChild(row);
  });
}

document.getElementById("addFlow").onclick = async () => {
  const id = newFlowEl.value.trim();
  if (!id) return;
  const flows = await getFlows();
  if (!flows.includes(id)) flows.push(id);
  await setFlows(flows);
  newFlowEl.value = "";
  void render();
};

async function refreshResult() {
  const { leviLastResult } = await chrome.storage.local.get("leviLastResult");
  resultEl.textContent = leviLastResult
    ? JSON.stringify(leviLastResult, null, 1)
    : "—";
}

void render();
void refreshResult();
setInterval(refreshResult, 1000);
