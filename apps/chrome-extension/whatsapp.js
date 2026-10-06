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

  function extractJid(value) {
    const text = String(value || '');
    const match = text.match(/([0-9A-Za-z._:-]+@(?:g\.us|c\.us|s\.whatsapp\.net|lid))/i);
    return match ? match[1] : null;
  }

  function phoneFromJid(jid) {
    const match = String(jid || '').match(/^(\d+)@(?:c\.us|s\.whatsapp\.net)$/i);
    return match ? match[1] : null;
  }

  function contactRecordFromElement(element) {
    if (!element) return null;
    const name = cleanContactName(element.getAttribute?.('title') || element.textContent);
    if (!name) return null;

    const row = element.closest?.(
      '[role="listitem"], [role="button"], div[tabindex="-1"], [data-testid*="cell-frame"]'
    ) || element.parentElement || element;

    const identityValues = [];
    const pushAttrs = (node) => {
      if (!node?.getAttribute) return;
      for (const attr of ['data-id', 'data-jid', 'data-chat-id', 'data-contact-id', 'href']) {
        const value = node.getAttribute(attr);
        if (value) identityValues.push(value);
      }
    };

    pushAttrs(row);
    pushAttrs(element);
    for (const node of Array.from(row.querySelectorAll?.(
      '[data-id], [data-jid], [data-chat-id], [data-contact-id], a[href]'
    ) || []).slice(0, 20)) {
      pushAttrs(node);
    }

    let jid = null;
    for (const value of identityValues) {
      jid = extractJid(value);
      if (jid) break;
    }

    const phone = phoneFromJid(jid);
    const ariaText = [
      row.getAttribute?.('aria-label'),
      row.getAttribute?.('title'),
      row.textContent
    ].filter(Boolean).join(' ').toLowerCase();

    const looksGroup = Boolean(
      (jid && /@g\.us$/i.test(jid)) ||
      row.querySelector?.('[data-icon*="group"], [aria-label*="group" i]') ||
      /\bgroup\b/.test(ariaText)
    );

    return {
      name,
      display_name: name,
      jid: jid || null,
      chat_id: jid || null,
      phone: phone || null,
      type: looksGroup ? 'group' : (jid ? 'contact' : 'unknown')
    };
  }

  function recordKey(record) {
    if (!record) return '';
    if (record.jid) return `jid:${String(record.jid).toLowerCase()}`;
    if (record.phone) return `phone:${String(record.phone).replace(/\D+/g, '')}`;
    return `name:${M.normalize(record.name)}:${record.type || 'unknown'}`;
  }

  function mergeRecordMap(target, records) {
    for (const record of records || []) {
      if (!record?.name) continue;
      const key = recordKey(record);
      if (!key) continue;
      const existing = target.get(key);
      target.set(key, existing ? {
        ...existing,
        ...record,
        jid: record.jid || existing.jid || null,
        chat_id: record.chat_id || existing.chat_id || null,
        phone: record.phone || existing.phone || null,
        type: record.type !== 'unknown' ? record.type : (existing.type || 'unknown')
      } : record);
    }
  }

  function collectVisibleContactRecords(root = document) {
    const records = new Map();
    const titled = Array.from(root.querySelectorAll('[title]')).filter(M.visible);
    for (const element of titled) {
      const record = contactRecordFromElement(element);
      if (record) mergeRecordMap(records, [record]);
    }
    return Array.from(records.values());
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
    const contacts = collectVisibleContactRecords(pane)
      .sort((a, b) => String(a.name).localeCompare(String(b.name)));
    const signature = contacts
      .map(record => `${recordKey(record)}|${record.name}|${record.type}`)
      .join('\u0000');
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

  function findContactPickerBackButton() {
    return M.findByAriaContains('back', '[aria-label]') ||
      Array.from(document.querySelectorAll('button, [role="button"]'))
        .filter(M.visible)
        .find(el => {
          const title = M.normalize(el.getAttribute('title'));
          const aria = M.normalize(el.getAttribute('aria-label'));
          return title === 'back' || aria === 'back' || Boolean(el.querySelector('[data-icon*="back"]'));
        }) ||
      document.querySelector('[data-icon*="back"]')?.closest('[role="button"], button') ||
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

  async function scanScrollableRecords(container, collected, source, maxSteps = 80) {
    if (!container) return false;
    const originalScrollTop = container.scrollTop;
    let reachedBottom = false;
    let stableRounds = 0;
    let previousSize = collected.size;

    container.scrollTop = 0;
    container.dispatchEvent(new Event('scroll', { bubbles: true }));
    await M.sleep(250);

    for (let i = 0; i < maxSteps; i += 1) {
      mergeRecordMap(collected, collectVisibleContactRecords(container));
      reportContacts(Array.from(collected.values()), source);

      const maxScroll = Math.max(0, container.scrollHeight - container.clientHeight);
      if (container.scrollTop >= maxScroll - 8) {
        reachedBottom = true;
        break;
      }

      container.scrollTop = Math.min(
        maxScroll,
        container.scrollTop + Math.max(420, container.clientHeight * 0.82)
      );
      container.dispatchEvent(new Event('scroll', { bubbles: true }));
      await M.sleep(260);

      if (collected.size === previousSize) stableRounds += 1;
      else stableRounds = 0;
      previousSize = collected.size;

      if (stableRounds >= 10) break;
    }

    container.scrollTop = originalScrollTop;
    container.dispatchEvent(new Event('scroll', { bubbles: true }));
    return reachedBottom;
  }

  async function syncAllContacts() {
    const collected = new Map();

    // First scan the full chat list. This is where WhatsApp groups are most
    // reliably exposed, including group JIDs when the DOM provides them.
    const sidebar = document.querySelector('#pane-side');
    let chatsComplete = false;
    if (sidebar) {
      chatsComplete = await scanScrollableRecords(
        sidebar,
        collected,
        'whatsapp_chat_sidebar',
        100
      );
    }
    reportVisibleSidebarContacts();

    // Then scan the New Chat picker for contacts not currently present in chats.
    const newChat = await M.waitFor(findNewChatButton, 8000);
    if (!newChat) {
      reportContacts(Array.from(collected.values()), 'whatsapp_visible_fallback');
      return {
        success: collected.size > 0,
        verified: collected.size > 0,
        contacts_synced: collected.size,
        complete: false,
        partial: true,
        chat_scan_complete: chatsComplete,
        error: collected.size > 0
          ? 'WhatsApp New chat button was not found; MAYA synced the available chats/groups only.'
          : 'WhatsApp contact UI was not available.'
      };
    }

    newChat.click();
    await M.sleep(800);

    mergeRecordMap(collected, collectVisibleContactRecords(document));
    const pickerContainer = findContactScrollContainer();
    const contactsComplete = await scanScrollableRecords(
      pickerContainer,
      collected,
      'whatsapp_contact_picker',
      100
    );
    mergeRecordMap(collected, collectVisibleContactRecords(document));
    reportContacts(Array.from(collected.values()), 'whatsapp_full_sync');

    const backButton = findContactPickerBackButton();
    if (backButton) {
      backButton.click();
    } else {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
      document.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape', code: 'Escape', bubbles: true }));
    }

    const records = Array.from(collected.values());
    const groups = records.filter(record => record.type === 'group').length;
    const contacts = records.filter(record => record.type === 'contact').length;

    return {
      success: records.length > 0,
      verified: records.length > 0,
      contacts_synced: records.length,
      groups_synced: groups,
      typed_contacts_synced: contacts,
      complete: Boolean(chatsComplete && contactsComplete),
      partial: !(chatsComplete && contactsComplete),
      chat_scan_complete: chatsComplete,
      contact_picker_complete: contactsComplete
    };
  }

  function currentChatRecord(nameHint = '') {
    const main = document.querySelector('#main');
    if (!main) return null;

    const jidCandidates = new Set();
    for (const node of Array.from(main.querySelectorAll('[data-id], [data-jid], [data-chat-id]')).slice(-120)) {
      for (const attr of ['data-id', 'data-jid', 'data-chat-id']) {
        const jid = extractJid(node.getAttribute(attr));
        if (jid) jidCandidates.add(jid);
      }
    }

    const jids = Array.from(jidCandidates);
    const groupJid = jids.find(jid => /@g\.us$/i.test(jid)) || null;
    const directJids = jids.filter(jid => /@(?:c\.us|s\.whatsapp\.net)$/i.test(jid));
    const jid = groupJid || (directJids.length === 1 ? directJids[0] : null);

    const header = main.querySelector('header');
    const headerTitles = Array.from(header?.querySelectorAll?.('[title]') || [])
      .map(el => cleanContactName(el.getAttribute('title')))
      .filter(Boolean);
    const name = headerTitles[0] || cleanContactName(nameHint);
    if (!name) return null;

    const record = {
      name,
      display_name: name,
      jid: jid || null,
      chat_id: jid || null,
      phone: phoneFromJid(jid),
      type: groupJid ? 'group' : (jid ? 'contact' : 'unknown')
    };
    return record;
  }

  function findChatHeaderClickable() {
    const header = document.querySelector('#main header');
    if (!header) return null;
    return Array.from(header.querySelectorAll('[role="button"], button, [tabindex="0"]'))
      .filter(M.visible)[0] || header;
  }

  function findVisibleContactInfoRoot() {
    const main = document.querySelector('#main');
    const candidates = Array.from(document.querySelectorAll(
      '[role="dialog"], [role="complementary"], [data-testid*="drawer"], [data-testid*="contact-info"], [data-testid*="group-info"]'
    )).filter(M.visible);

    // Never inspect the chat message pane itself for a contact phone number.
    // Only accept a separate info surface opened from the chat header.
    return candidates.find(node => !main || !main.contains(node)) || null;
  }

  function visiblePhoneFromContactInfo() {
    const root = findVisibleContactInfoRoot();
    if (!root) return null;

    const texts = Array.from(root.querySelectorAll('span, div, a'))
      .filter(M.visible)
      .map(el => String(el.textContent || '').trim())
      .filter(text => text.length >= 7 && text.length <= 40);

    for (const text of texts) {
      const match = text.match(/(?:\+\s*)?\d(?:[\s()-]*\d){6,14}/);
      if (match) {
        const digits = match[0].replace(/\D+/g, '');
        if (digits.length >= 7 && digits.length <= 15) return digits;
      }
    }
    return null;
  }

  async function inspectCurrentContact(nameHint = '') {
    let record = currentChatRecord(nameHint) || {
      name: cleanContactName(nameHint) || String(nameHint || '').trim(),
      display_name: cleanContactName(nameHint) || String(nameHint || '').trim(),
      jid: null,
      chat_id: null,
      phone: null,
      type: 'unknown'
    };

    const header = findChatHeaderClickable();
    if (header) {
      header.click();
      await M.sleep(700);
      const visiblePhone = visiblePhoneFromContactInfo();
      if (!record.phone && visiblePhone) record.phone = visiblePhone;

      const infoRoot = findVisibleContactInfoRoot();
      const infoText = M.normalize(infoRoot?.innerText || '');
      if (record.type === 'unknown' && (infoText.includes('group info') || infoText.includes('participants'))) {
        record.type = 'group';
      }

      const close = M.findByAriaContains('close', '[aria-label]') ||
        M.findByAriaContains('back', '[aria-label]');
      if (close) close.click();
      else {
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
      }
    }

    reportContacts([record], 'whatsapp_live_contact_inspection');
    return record;
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
      titled.map(el => contactRecordFromElement(el)).filter(Boolean),
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

  function extractVisibleMessages(limit = 1) {
    const main = document.querySelector('#main');
    if (!main) return [];

    const candidates = Array.from(main.querySelectorAll(
      '[data-testid="msg-container"], .message-in, .message-out'
    ));
    const unique = [];
    const seen = new Set();

    for (const element of candidates) {
      const container = element.closest?.(
        '[data-testid="msg-container"], .message-in, .message-out'
      ) || element;
      if (seen.has(container)) continue;
      seen.add(container);

      const textNodes = Array.from(container.querySelectorAll(
        'span.selectable-text, [data-pre-plain-text] span, [dir="ltr"]'
      ));
      let text = textNodes
        .map(node => String(node.textContent || '').trim())
        .filter(Boolean)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();

      if (!text) {
        text = String(container.innerText || '')
          .replace(/\s+/g, ' ')
          .trim();
      }
      if (!text) continue;

      const metaNode = container.querySelector('[data-pre-plain-text]');
      const meta = String(metaNode?.getAttribute('data-pre-plain-text') || '').trim();
      let sender = null;
      let timestamp = null;
      const metaMatch = meta.match(/^\[([^\]]+)\]\s*([^:]+):\s*$/);
      if (metaMatch) {
        timestamp = metaMatch[1].trim();
        sender = metaMatch[2].trim();
      }

      const outgoing = container.classList.contains('message-out') ||
        Boolean(container.closest('.message-out'));
      const incoming = container.classList.contains('message-in') ||
        Boolean(container.closest('.message-in'));

      unique.push({
        text,
        sender,
        timestamp,
        direction: outgoing ? 'outgoing' : (incoming ? 'incoming' : 'unknown')
      });
    }

    return unique.slice(-Math.max(1, Math.min(Number(limit) || 1, 20)));
  }

  async function handle(command) {
    if (command.action === 'sync_contacts') {
      return await syncAllContacts();
    }

    const recipient = String(command.recipient || '').trim();

    if (command.action === 'inspect_contact') {
      const selected = await selectContact(recipient);
      if (!selected.ok) {
        return { success: false, verified: false, error: selected.error };
      }
      await M.sleep(500);
      const record = await inspectCurrentContact(recipient);
      return {
        success: Boolean(record?.name),
        verified: Boolean(record?.name),
        service: 'whatsapp',
        recipient,
        record
      };
    }

    if (command.action === 'read_messages') {
      const useCurrent = ['current chat', 'current conversation'].includes(M.normalize(recipient));
      if (!useCurrent) {
        const selected = await selectContact(recipient);
        if (!selected.ok) {
          return { success: false, verified: false, error: selected.error };
        }
        await M.sleep(500);
      }

      const composer = await M.waitFor(findComposer, 7000);
      if (!composer) {
        return {
          success: false,
          verified: false,
          error: 'WhatsApp chat did not become active, so MAYA refused to report messages.'
        };
      }

      const messages = extractVisibleMessages(command.limit || 1);
      return {
        success: true,
        verified: true,
        service: 'whatsapp',
        recipient: recipient || 'current chat',
        messages,
        count: messages.length,
        latest: messages.length ? messages[messages.length - 1] : null,
        live_read: true
      };
    }
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

  // Full contact/group synchronization is explicit. MAYA may still enrich a
  // record when the user searches/opens that exact chat, but it does not crawl
  // the sidebar continuously in the background.
})();
