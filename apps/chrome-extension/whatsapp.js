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
})();
