const MAYA_API = 'http://127.0.0.1:5000/api';
let sessionToken = null;
const inFlight = new Set();
let browserActionBusy = false;

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
      `${MAYA_API}/communication/next?service=${encodeURIComponent(service)}&tab_id=${encodeURIComponent(tabId)}`,
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
        tab_count: windowTabs?.length ?? null,
        extension_version: chrome.runtime.getManifest().version
      })
    });

    if (response.status === 401) {
      sessionToken = null;
    }
  } catch {
    // MAYA may be offline or Chrome may hide metadata for protected pages.
  }
}

async function pollBrowserAction() {
  if (browserActionBusy) return;
  browserActionBusy = true;
  try {
    const token = await getToken();
    const response = await fetch(`${MAYA_API}/browser/action/next`, {
      headers: { 'X-Maya-Token': token }
    });
    if (response.status === 401) {
      sessionToken = null;
      return;
    }
    if (!response.ok) return;
    const data = await response.json();
    const action = data?.action;
    if (!action?.action_id) return;

    let result = {
      success: false,
      verified: false,
      error: 'Unsupported browser action.'
    };

    if (action.type === 'focus_service') {
      const service = String(action.service || '').toLowerCase();
      const servicePrefixes = {
        whatsapp: 'https://web.whatsapp.com/',
        gmail: 'https://mail.google.com/',
        telegram: 'https://web.telegram.org/'
      };
      const targetUrl = String(action.url || servicePrefixes[service] || '');
      const forceNew = Boolean(action.force_new);

      if (!targetUrl) {
        result = {
          success: false,
          verified: false,
          error: `Unsupported browser service: ${service}`
        };
      } else {
        let targetTab = null;
        if (!forceNew) {
          const candidates = await chrome.tabs.query({});
          targetTab = candidates.find(tab =>
            typeof tab.url === 'string' &&
            tab.url.startsWith(targetUrl)
          ) || null;
        }

        if (targetTab?.id != null) {
          await chrome.tabs.update(targetTab.id, { active: true });
          if (targetTab.windowId != null) {
            await chrome.windows.update(targetTab.windowId, { focused: true });
          }
          result = {
            success: true,
            verified: true,
            reused_existing: true,
            tab_id: targetTab.id,
            window_id: targetTab.windowId ?? null,
            url: targetTab.url || targetUrl,
            service
          };
        } else {
          const created = await chrome.tabs.create({ url: targetUrl, active: true });
          result = {
            success: Boolean(created?.id),
            verified: Boolean(created?.id),
            reused_existing: false,
            created_new: true,
            tab_id: created?.id ?? null,
            window_id: created?.windowId ?? null,
            url: created?.url || targetUrl,
            service
          };
        }
      }
    }

    await fetch(`${MAYA_API}/browser/action/result`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Maya-Token': token
      },
      body: JSON.stringify({
        action_id: action.action_id,
        result
      })
    });
    reportActiveTabContext();
  } catch {
    // MAYA may be offline.
  } finally {
    browserActionBusy = false;
  }
}

// MV3 service workers may sleep, so this timer is only a best-effort path.
setInterval(pollBrowserAction, 1000);

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

async function postContacts(service, contacts, source = 'browser') {
  try {
    if (!service || !Array.isArray(contacts) || contacts.length === 0) return;
    const token = await getToken();
    const response = await fetch(`${MAYA_API}/communication/contacts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Maya-Token': token
      },
      body: JSON.stringify({ service, contacts, source })
    });
    if (response.status === 401) sessionToken = null;
  } catch {
    // Contact discovery is opportunistic; MAYA may be offline.
  }
}

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
    // A content-script poll wakes an MV3 background worker. Process pending
    // privileged browser actions here too, instead of depending on setInterval
    // continuing to run while Chrome has suspended the service worker.
    pollBrowserAction();
    pollForCommand(message.service, sender.tab.id);
    return;
  }

  if (message?.type === 'maya-contact-sync' && message.service && Array.isArray(message.contacts)) {
    postContacts(message.service, message.contacts, message.source || 'browser');
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
