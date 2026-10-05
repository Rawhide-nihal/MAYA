(() => {
  const M = window.MayaBridgeCommon;
  if (!M) return;

  function findSearchBox() {
    return Array.from(document.querySelectorAll('input, [contenteditable="true"]'))
      .filter(M.visible)
      .find(el => {
        const placeholder = M.normalize(el.getAttribute('placeholder'));
        const aria = M.normalize(el.getAttribute('aria-label'));
        return placeholder === 'search' ||
          aria === 'search' ||
          aria.includes('search');
      }) || null;
  }

  function findComposer() {
    return Array.from(document.querySelectorAll('[contenteditable="true"]'))
      .filter(M.visible)
      .find(el => {
        const placeholder = M.normalize(el.getAttribute('data-placeholder'));
        const aria = M.normalize(el.getAttribute('aria-label'));
        const cls = String(el.className || '').toLowerCase();
        return placeholder.includes('message') ||
          aria.includes('message') ||
          cls.includes('input-message-input');
      }) || null;
  }

  function findSendButton() {
    return Array.from(document.querySelectorAll('button, [role="button"]'))
      .filter(M.visible)
      .find(el => {
        const aria = M.normalize(el.getAttribute('aria-label'));
        const title = M.normalize(el.getAttribute('title'));
        const cls = String(el.className || '').toLowerCase();
        return aria === 'send' ||
          title === 'send' ||
          cls.includes('btn-send');
      }) || null;
  }

  async function selectContact(recipient) {
    const search = await M.waitFor(findSearchBox, 12000);
    if (!search) return { ok: false, error: 'Telegram search field was not found.' };

    if (search instanceof HTMLInputElement) M.setInputValue(search, recipient);
    else M.setEditableText(search, recipient);

    await M.sleep(1000);
    const resultPane =
      document.querySelector('#column-left') ||
      document.querySelector('.sidebar-left') ||
      document;
    const target = M.normalize(recipient);
    const matches = Array.from(resultPane.querySelectorAll('span, div, h3, h4'))
      .filter(M.visible)
      .filter(el => M.normalize(el.textContent) === target);

    const rows = Array.from(new Set(
      matches.map(el => el.closest('[role="listitem"], .ListItem, li, a, [role="button"]') || el)
    ));

    if (rows.length !== 1) {
      return {
        ok: false,
        error: rows.length === 0
          ? `No exact Telegram contact named “${recipient}” was found.`
          : `Multiple Telegram matches exist for “${recipient}”. MAYA refused to guess.`
      };
    }

    rows[0].click();
    return { ok: true };
  }

  async function handle(command) {
    const recipient = String(command.recipient || '').trim();
    const message = String(command.message || '').trim();

    const selected = await selectContact(recipient);
    if (!selected.ok) {
      return { success: false, verified: false, error: selected.error };
    }

    const composer = await M.waitFor(findComposer, 7000);
    if (!composer) {
      return { success: false, verified: false, error: 'Telegram message composer was not found.' };
    }

    M.setEditableText(composer, message);

    if (command.action === 'compose') {
      return {
        success: true,
        verified: true,
        prepared: true,
        sent: false,
        service: 'telegram',
        recipient
      };
    }

    const sendButton = await M.waitFor(findSendButton, 3500);
    if (!sendButton) {
      return { success: false, verified: false, error: 'Telegram Send button was not found.' };
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
      service: 'telegram',
      recipient,
      send_attempted: true,
      error: emptied ? undefined : 'MAYA clicked Send, but Telegram did not expose a verified sent state. Check the conversation before retrying to avoid duplicates.'
    };
  }

  M.start('telegram', handle);
})();
