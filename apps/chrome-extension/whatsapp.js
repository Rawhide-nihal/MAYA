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
    const exact = M.exactTextElements(recipient, '[title], span, div')
      .filter(el => {
        const title = M.normalize(el.getAttribute('title'));
        return !title || title === M.normalize(recipient);
      });

    const unique = Array.from(new Set(exact));
    if (unique.length !== 1) {
      return {
        ok: false,
        error: unique.length === 0
          ? `No exact WhatsApp contact named “${recipient}” was found.`
          : `Multiple WhatsApp matches exist for “${recipient}”. MAYA refused to guess.`
      };
    }

    const clickable = unique[0].closest('[role="listitem"], [role="button"]') || unique[0];
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
      error: emptied ? undefined : 'WhatsApp did not reach a verified sent state.'
    };
  }

  M.start('whatsapp', handle);
})();
