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
    const windowTabs = await chrome.tabs.query({ windowId: tab.windowId });

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
        window_id: tab.windowId ?? null,
        tab_count: windowTabs?.length ?? null
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

chrome.tabs.onActivated.addListener(() => {
  reportActiveTabContext();
});

chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (changeInfo.status === 'complete' || changeInfo.url || changeInfo.title) {
    reportActiveTabContext();
  }
});

chrome.windows.onFocusChanged.addListener(() => {
  reportActiveTabContext();
});

async function fetchCommandAttachment(commandId) {
  const token = await getToken();
  const response = await fetch(
    `${MAYA_API}/communication/attachment/${encodeURIComponent(commandId)}`,
    { headers: { 'X-Maya-Token': token } }
  );
  if (response.status === 401) sessionToken = null;
  if (!response.ok) {
    let errorText = `Attachment bridge returned HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data?.error) errorText = data.error;
    } catch {}
    throw new Error(errorText);
  }

  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }

  const disposition = response.headers.get('Content-Disposition') || '';
  const filenameMatch = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
  const filename = filenameMatch
    ? decodeURIComponent(filenameMatch[1].replace(/^"|"$/g, ''))
    : 'maya-attachment';

  return {
    success: true,
    name: filename,
    mime: response.headers.get('Content-Type') || 'application/octet-stream',
    size: bytes.length,
    base64: btoa(binary)
  };
}

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

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'maya-poll' && sender.tab?.id) {
    pollForCommand(message.service, sender.tab.id);
    return;
  }

  if (message?.type === 'maya-fetch-attachment' && message.commandId) {
    fetchCommandAttachment(message.commandId)
      .then(sendResponse)
      .catch(error => sendResponse({
        success: false,
        error: error instanceof Error ? error.message : String(error)
      }));
    return true;
  }

  if (message?.type === 'maya-result' && message.commandId) {
    postResult(message.commandId, message.result || {
      success: false,
      verified: false,
      error: 'Empty result from browser adapter.'
    });
  }
});
