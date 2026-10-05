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
    const recipient = String(command.recipient || '').trim();
    const message = String(command.message || '').trim();

    const selected = await selectContact(recipient);
    if (!selected.ok) {
      return { success: false, verified: false, error: selected.error };
    }

    const composer = await M.waitFor(findComposer, 7000);
    if (!composer) {
      return { success: false, verified: false, error: 'WhatsApp message composer was not found.' };
    }

    M.setEditableText(composer, message);

    if (command.action === 'compose') {
      return {
        success: true,
        verified: true,
        prepared: true,
        sent: false,
        service: 'whatsapp',
        recipient
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
      send_attempted: true,
      error: emptied ? undefined : 'MAYA clicked Send, but WhatsApp did not expose a verified sent state. Check the conversation before retrying to avoid duplicates.'
    };
  }

  M.start('whatsapp', handle);
})();
