const MAYA_API = 'http://127.0.0.1:5000/api';
let sessionToken = null;
const inFlight = new Set();

async function getToken() {
  if (sessionToken) return sessionToken;
  const response = await fetch(`${MAYA_API}/auth/token`, { method: 'GET' });
  if (!response.ok) throw new Error(`MAYA auth bootstrap failed: ${response.status}`);
  const data = await response.json();
  if (!data.token) throw new Error('MAYA did not return an auth token.');
  sessionToken = data.token;
  return sessionToken;
}

async function pollForCommand(service, tabId) {
  if (!service || !tabId || inFlight.has(service)) return;
  inFlight.add(service);
  try {
    const token = await getToken();
    const response = await fetch(
      `${MAYA_API}/communication/next?service=${encodeURIComponent(service)}`,
      {
        method: 'GET',
        headers: { 'X-Maya-Token': token }
      }
    );
    if (response.status === 401) {
      sessionToken = null;
      return;
    }
    if (!response.ok) return;
    const data = await response.json();
    if (data.command) {
      await chrome.tabs.sendMessage(tabId, {
        type: 'maya-command',
        command: data.command
      });
    }
  } catch (error) {
    // MAYA may simply be offline; content scripts keep polling.
  } finally {
    inFlight.delete(service);
  }
}

async function reportActiveTabContext() {
  try {
    const token = await getToken();
    const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    const tab = tabs?.[0];
    if (!tab) return;

    const response = await fetch(`${MAYA_API}/browser/context`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Maya-Token': token
      },
      body: JSON.stringify({
        title: tab.title || '',
        url: tab.url || '',
        tab_id: tab.id ?? null,
        window_id: tab.windowId ?? null
      })
    });

    if (response.status === 401) {
      sessionToken = null;
    }
  } catch {
    // MAYA may be offline or Chrome may hide metadata for protected pages.
  }
}

setInterval(reportActiveTabContext, 1500);
reportActiveTabContext();

async function postResult(commandId, result) {
  try {
    const token = await getToken();
    const response = await fetch(`${MAYA_API}/communication/result`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Maya-Token': token
      },
      body: JSON.stringify({
        command_id: commandId,
        result
      })
    });
    if (response.status === 401) sessionToken = null;
  } catch (error) {
    // The backend timeout will report a bridge failure if this cannot be delivered.
  }
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type === 'maya-poll' && sender.tab?.id) {
    pollForCommand(message.service, sender.tab.id);
    return;
  }

  if (message?.type === 'maya-result' && message.commandId) {
    postResult(message.commandId, message.result || {
      success: false,
      verified: false,
      error: 'Empty result from browser adapter.'
    });
  }
});
