(() => {
  const M = window.MayaBridgeCommon;
  if (!M) return;

  function findComposeButton() {
    return Array.from(document.querySelectorAll('[role="button"], button'))
      .filter(M.visible)
      .find(el => {
        const label = M.normalize(el.getAttribute('aria-label'));
        const text = M.normalize(el.textContent);
        return label === 'compose' || text === 'compose';
      }) || null;
  }

  function findRecipientInput() {
    const candidates = Array.from(document.querySelectorAll('input'))
      .filter(M.visible);
    return candidates.find(el => {
      const aria = M.normalize(el.getAttribute('aria-label'));
      const name = M.normalize(el.getAttribute('name'));
      return name === 'to' ||
        aria.includes('to recipients') ||
        aria === 'recipients' ||
        aria.startsWith('to ');
    }) || null;
  }

  function findSubjectInput() {
    return document.querySelector('input[name="subjectbox"]');
  }

  function findBody() {
    return Array.from(document.querySelectorAll('[contenteditable="true"]'))
      .filter(M.visible)
      .find(el => {
        const aria = M.normalize(el.getAttribute('aria-label'));
        const role = M.normalize(el.getAttribute('role'));
        return aria.includes('message body') || role === 'textbox';
      }) || null;
  }

  function findSendButton() {
    return Array.from(document.querySelectorAll('[role="button"], button'))
      .filter(M.visible)
      .find(el => {
        const aria = M.normalize(el.getAttribute('aria-label'));
        const tooltip = M.normalize(el.getAttribute('data-tooltip'));
        const text = M.normalize(el.textContent);
        return aria === 'send' ||
          aria.startsWith('send ') ||
          tooltip === 'send' ||
          tooltip.startsWith('send ') ||
          text === 'send';
      }) || null;
  }

  async function handle(command) {
    const recipient = String(command.recipient || '').trim();
    const message = String(command.message || '').trim();
    const subject = String(command.subject || '').trim();

    if (!recipient.includes('@')) {
      return {
        success: false,
        verified: false,
        error: 'For Gmail, MAYA currently requires an exact email address to avoid choosing the wrong contact.'
      };
    }

    let recipientInput = findRecipientInput();
    if (!recipientInput) {
      const compose = await M.waitFor(findComposeButton, 10000);
      if (!compose) {
        return {
          success: false,
          verified: false,
          error: 'Gmail Compose button was not found. Make sure Gmail is fully loaded and signed in.'
        };
      }
      compose.click();
      recipientInput = await M.waitFor(findRecipientInput, 8000);
    }

    if (!recipientInput) {
      return { success: false, verified: false, error: 'Gmail recipient field was not found.' };
    }

    M.setInputValue(recipientInput, recipient);
    recipientInput.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter',
      code: 'Enter',
      bubbles: true
    }));
    recipientInput.dispatchEvent(new KeyboardEvent('keyup', {
      key: 'Enter',
      code: 'Enter',
      bubbles: true
    }));

    const subjectInput = await M.waitFor(findSubjectInput, 5000);
    if (subjectInput && subject) M.setInputValue(subjectInput, subject);

    const body = await M.waitFor(findBody, 5000);
    if (!body) {
      return { success: false, verified: false, error: 'Gmail message body was not found.' };
    }
    M.setEditableText(body, message);

    if (command.action === 'compose') {
      return {
        success: true,
        verified: true,
        prepared: true,
        sent: false,
        service: 'gmail',
        recipient
      };
    }

    const sendButton = await M.waitFor(findSendButton, 5000);
    if (!sendButton) {
      return { success: false, verified: false, error: 'Gmail Send button was not found.' };
    }
    sendButton.click();

    const sentNotice = await M.waitFor(() => {
      return Array.from(document.querySelectorAll('[role="alert"], [role="status"], div'))
        .filter(M.visible)
        .find(el => M.normalize(el.textContent).includes('message sent')) || null;
    }, 8000);

    return {
      success: Boolean(sentNotice),
      verified: Boolean(sentNotice),
      sent: Boolean(sentNotice),
      service: 'gmail',
      recipient,
      send_attempted: true,
      error: sentNotice ? undefined : 'MAYA clicked Send, but Gmail did not expose a verified “Message sent” state. Check Sent mail before retrying to avoid duplicates.'
    };
  }

  M.start('gmail', handle);
})();
