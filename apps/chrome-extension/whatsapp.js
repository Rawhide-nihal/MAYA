(() => {
  const M = window.MayaBridgeCommon;
  if (!M) return;

  function findSearchBox() {
    return Array.from(document.querySelectorAll('[contenteditable="true"], input'))
      .filter(M.visible)
      .find(el => {
        const aria = M.normalize(el.getAttribute('aria-label'));
        const placeholder = M.normalize(el.getAttribute('placeholder'));
        return aria.includes('search input') ||
          aria === 'search' ||
          placeholder === 'search';
      }) || null;
  }

  let lastSidebarContactSignature = '';

  const CONTACT_UI_TITLES = new Set([
    'new chat', 'search', 'archived', 'communities', 'status', 'channels',
    'settings', 'profile', 'new group', 'contacts', 'frequently contacted'
  ]);

  function cleanContactName(value) {
    const name = String(value || '').trim().replace(/\s+/g, ' ');
    const normalized = M.normalize(name);
    if (!name || name.length > 160 || CONTACT_UI_TITLES.has(normalized)) return null;
    if (/^\d{1,2}:\d{2}/.test(name)) return null;
    return name;
  }

  function collectVisibleContactNames(root = document) {
    const names = new Set();
    const titled = Array.from(root.querySelectorAll('[title]')).filter(M.visible);
    for (const element of titled) {
      const name = cleanContactName(element.getAttribute('title'));
      if (name) names.add(name);
    }
    return Array.from(names);
  }

  function reportContacts(contacts, source) {
    if (!Array.isArray(contacts) || contacts.length === 0) return;
    chrome.runtime.sendMessage({
      type: 'maya-contact-sync',
      service: 'whatsapp',
      contacts,
      source
    });
  }

  function reportVisibleSidebarContacts() {
    const pane = document.querySelector('#pane-side');
    if (!pane) return;
    const contacts = collectVisibleContactNames(pane).sort((a, b) => a.localeCompare(b));
    const signature = contacts.join('\u0000');
    if (!contacts.length || signature === lastSidebarContactSignature) return;
    lastSidebarContactSignature = signature;
    reportContacts(contacts, 'whatsapp_sidebar');
  }

  function findNewChatButton() {
    return M.findByAriaContains('new chat', '[aria-label]') ||
      Array.from(document.querySelectorAll('button, [role="button"]'))
        .filter(M.visible)
        .find(el => {
          const title = M.normalize(el.getAttribute('title'));
          const aria = M.normalize(el.getAttribute('aria-label'));
          const icon = el.querySelector('[data-icon*="new-chat"]');
          return title.includes('new chat') || aria.includes('new chat') || Boolean(icon);
        }) ||
      document.querySelector('[data-icon*="new-chat"]')?.closest('[role="button"], button') ||
      null;
  }

  function findContactScrollContainer() {
    const candidates = Array.from(document.querySelectorAll('div'))
      .filter(M.visible)
      .filter(el => el.scrollHeight > el.clientHeight + 120)
      .filter(el => el.querySelectorAll('[title]').length >= 2);

    candidates.sort((a, b) => {
      const aScore = a.querySelectorAll('[title]').length + (a.scrollHeight - a.clientHeight) / 100;
      const bScore = b.querySelectorAll('[title]').length + (b.scrollHeight - b.clientHeight) / 100;
      return bScore - aScore;
    });
    return candidates[0] || null;
  }

  async function syncAllContacts() {
    reportVisibleSidebarContacts();

    const newChat = await M.waitFor(findNewChatButton, 8000);
    if (!newChat) {
      const visible = collectVisibleContactNames(document.querySelector('#pane-side') || document);
      reportContacts(visible, 'whatsapp_visible_fallback');
      return {
        success: visible.length > 0,
        verified: visible.length > 0,
        contacts_synced: visible.length,
        complete: false,
        error: visible.length > 0
          ? 'WhatsApp New chat button was not found; MAYA synced the currently loaded chats only.'
          : 'WhatsApp contact UI was not available.'
      };
    }

    newChat.click();
    await M.sleep(800);

    const collected = new Set(collectVisibleContactNames(document));
    let container = findContactScrollContainer();
    let reachedBottom = false;
    let stableRounds = 0;
    let previousCount = collected.size;

    if (container) {
      for (let i = 0; i < 60; i += 1) {
        collectVisibleContactNames(container).forEach(name => collected.add(name));
        reportContacts(Array.from(collected), 'whatsapp_contact_picker');

        const maxScroll = Math.max(0, container.scrollHeight - container.clientHeight);
        if (container.scrollTop >= maxScroll - 8) {
          reachedBottom = true;
          break;
        }

        container.scrollTop = Math.min(maxScroll, container.scrollTop + Math.max(400, container.clientHeight * 0.8));
        container.dispatchEvent(new Event('scroll', { bubbles: true }));
        await M.sleep(260);

        if (collected.size === previousCount) stableRounds += 1;
        else stableRounds = 0;
        previousCount = collected.size;

        // Virtualized lists can recycle the same DOM. Refresh the best
        // scroll container in case WhatsApp changed panel structure.
        if (stableRounds >= 6) {
          const refreshed = findContactScrollContainer();
          if (refreshed) container = refreshed;
          stableRounds = 0;
        }
      }
    }

    collectVisibleContactNames(document).forEach(name => collected.add(name));
    reportContacts(Array.from(collected), 'whatsapp_contact_picker');

    // Close the picker without selecting anybody.
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
    document.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape', code: 'Escape', bubbles: true }));

    return {
      success: collected.size > 0,
      verified: collected.size > 0,
      contacts_synced: collected.size,
      complete: reachedBottom,
      partial: !reachedBottom
    };
  }

  function findComposer() {
    return Array.from(document.querySelectorAll('[contenteditable="true"]'))
      .filter(M.visible)
      .find(el => {
        const aria = M.normalize(el.getAttribute('aria-label'));
        const dataTab = el.getAttribute('data-tab');
        return aria.includes('type a message') ||
          aria.includes('message') ||
          dataTab === '10';
      }) || null;
  }

  function findAttachButton() {
    return M.findByAriaContains('attach', '[aria-label]') ||
      Array.from(document.querySelectorAll('button, [role="button"]'))
        .filter(M.visible)
        .find(el => M.normalize(el.getAttribute('title')).includes('attach')) ||
      null;
  }

  function findFileInput(mime = '') {
    const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
    if (!inputs.length) return null;
    if (String(mime).startsWith('image/')) {
      return inputs.find(input => M.normalize(input.getAttribute('accept')).includes('image')) || inputs[0];
    }
    return inputs.find(input => {
      const accept = M.normalize(input.getAttribute('accept'));
      return !accept || accept.includes('*') || !accept.includes('image');
    }) || inputs[0];
  }

  function findSendButton() {
    return M.findByAriaContains('send', 'button[aria-label], [role="button"][aria-label]') ||
      document.querySelector('button span[data-icon="send"]')?.closest('button') ||
      null;
  }

  async function selectContact(recipient) {
    const search = await M.waitFor(findSearchBox, 12000);
    if (!search) return { ok: false, error: 'WhatsApp search field was not found.' };

    if (search instanceof HTMLInputElement) M.setInputValue(search, recipient);
    else M.setEditableText(search, recipient);

    await M.sleep(900);
    const resultPane = document.querySelector('#pane-side') || document;
    const target = M.normalize(recipient);
    const titled = Array.from(resultPane.querySelectorAll('[title]'))
      .filter(M.visible)
      .filter(el => M.normalize(el.getAttribute('title')) === target);

    const rows = Array.from(new Set(
      titled.map(el => el.closest('[role="listitem"], [role="button"], div[tabindex="-1"]') || el)
    ));

    reportContacts(
      titled.map(el => cleanContactName(el.getAttribute('title'))).filter(Boolean),
      'whatsapp_search'
    );

    if (rows.length !== 1) {
      return {
        ok: false,
        error: rows.length === 0
          ? `No exact WhatsApp contact named “${recipient}” was found.`
          : `Multiple WhatsApp matches exist for “${recipient}”. MAYA refused to guess.`
      };
    }

    rows[0].click();
    return { ok: true };
  }

  async function handle(command) {
    if (command.action === 'sync_contacts') {
      return await syncAllContacts();
    }

    const recipient = String(command.recipient || '').trim();
    const message = String(command.message || '').trim();

    const useCurrentChat = ['current chat', 'current conversation'].includes(M.normalize(recipient));
    if (!useCurrentChat) {
      const selected = await selectContact(recipient);
      if (!selected.ok) {
        return { success: false, verified: false, error: selected.error };
      }
    } else {
      const currentComposer = await M.waitFor(findComposer, 5000);
      if (!currentComposer) {
        return {
          success: false,
          verified: false,
          error: 'No active WhatsApp chat is open. MAYA refused to guess a recipient.'
        };
      }
    }

    let attachmentVerified = false;

    if (command.has_attachment) {
      const attachment = await M.fetchAttachment(command);
      let fileInput = findFileInput(attachment.mime);

      if (!fileInput) {
        const attachButton = await M.waitFor(findAttachButton, 4000);
        if (attachButton) attachButton.click();
        fileInput = await M.waitFor(() => findFileInput(attachment.mime), 5000);
      }

      if (!fileInput || !M.setFileInput(fileInput, attachment)) {
        return {
          success: false,
          verified: false,
          error: 'WhatsApp attachment input was not available or rejected the selected file.'
        };
      }

      const previewSend = await M.waitFor(findSendButton, 10000);
      if (!previewSend) {
        return {
          success: false,
          verified: false,
          error: 'WhatsApp did not expose an attachment preview/send state. MAYA refused to send.'
        };
      }
      attachmentVerified = true;

      if (message) {
        const caption = await M.waitFor(findComposer, 4000);
        if (caption) M.setEditableText(caption, message);
      }
    } else {
      const composer = await M.waitFor(findComposer, 7000);
      if (!composer) {
        return { success: false, verified: false, error: 'WhatsApp message composer was not found.' };
      }
      if (message) M.setEditableText(composer, message);
    }

    if (command.action === 'compose') {
      return {
        success: true,
        verified: true,
        prepared: true,
        sent: false,
        service: 'whatsapp',
        recipient,
        attachment_verified: attachmentVerified
      };
    }

    const sendButton = await M.waitFor(findSendButton, 4000);
    if (!sendButton) {
      return { success: false, verified: false, error: 'WhatsApp Send button was not found.' };
    }
    sendButton.click();

    const emptied = await M.waitFor(() => {
      const current = findComposer();
      return current && M.normalize(current.textContent) === '' ? current : null;
    }, 6000);

    return {
      success: Boolean(emptied),
      verified: Boolean(emptied),
      sent: Boolean(emptied),
      service: 'whatsapp',
      recipient,
      attachment_verified: attachmentVerified,
      send_attempted: true,
      error: emptied ? undefined : 'MAYA clicked Send, but WhatsApp did not expose a verified sent state. Check the conversation before retrying to avoid duplicates.'
    };
  }

  M.start('whatsapp', handle);

  reportVisibleSidebarContacts();
  setInterval(reportVisibleSidebarContacts, 5000);
})();
