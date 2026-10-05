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
    const matches = M.exactTextElements(recipient, 'span, div, h3, h4');
    const unique = Array.from(new Set(matches));

    if (unique.length !== 1) {
      return {
        ok: false,
        error: unique.length === 0
          ? `No exact Telegram contact named “${recipient}” was found.`
          : `Multiple Telegram matches exist for “${recipient}”. MAYA refused to guess.`
      };
    }

    const clickable = unique[0].closest('[role="listitem"], .ListItem, li, a, [role="button"]') || unique[0];
    clickable.click();
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
      error: emptied ? undefined : 'Telegram did not reach a verified sent state.'
    };
  }

  M.start('telegram', handle);
})();
