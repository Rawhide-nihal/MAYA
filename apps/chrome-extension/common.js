(() => {
  if (window.MayaBridgeCommon) return;

  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  function visible(element) {
    if (!element) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      rect.width > 0 &&
      rect.height > 0;
  }

  async function waitFor(getter, timeout = 10000, interval = 150) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      const value = getter();
      if (value) return value;
      await sleep(interval);
    }
    return null;
  }

  function setInputValue(input, value) {
    input.focus();
    const prototype = input instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
    if (descriptor?.set) descriptor.set.call(input, value);
    else input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function setEditableText(element, value) {
    element.focus();
    try {
      document.execCommand('selectAll', false, null);
      document.execCommand('insertText', false, value);
    } catch {
      element.textContent = value;
      element.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        inputType: 'insertText',
        data: value
      }));
    }
  }

  function normalize(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
  }

  function exactTextElements(text, selector = '*') {
    const target = normalize(text);
    return Array.from(document.querySelectorAll(selector))
      .filter(visible)
      .filter(element => normalize(element.textContent) === target);
  }

  function findByAriaContains(fragment, selector = '[aria-label]') {
    const target = normalize(fragment);
    return Array.from(document.querySelectorAll(selector))
      .filter(visible)
      .find(element => normalize(element.getAttribute('aria-label')).includes(target)) || null;
  }

  async function fetchAttachment(command) {
    if (!command?.has_attachment) return null;

    const payload = await chrome.runtime.sendMessage({
      type: 'maya-fetch-attachment',
      commandId: command.command_id
    });
    if (!payload?.success) {
      throw new Error(payload?.error || 'MAYA could not load the command attachment.');
    }

    const binary = atob(payload.base64 || '');
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }

    return {
      name: command.attachment_name || payload.name || 'maya-attachment',
      mime: command.attachment_mime || payload.mime || 'application/octet-stream',
      size: payload.size || bytes.length,
      file: new File(
        [bytes],
        command.attachment_name || payload.name || 'maya-attachment',
        { type: command.attachment_mime || payload.mime || 'application/octet-stream' }
      )
    };
  }

  function setFileInput(input, attachment) {
    if (!input || !attachment?.file) return false;
    try {
      const transfer = new DataTransfer();
      transfer.items.add(attachment.file);
      input.files = transfer.files;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return input.files?.length === 1;
    } catch {
      return false;
    }
  }

  async function deliver(command, handler) {
    let result;
    try {
      result = await handler(command);
    } catch (error) {
      result = {
        success: false,
        verified: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
    chrome.runtime.sendMessage({
      type: 'maya-result',
      commandId: command.command_id,
      result
    });
  }

  function start(service, handler) {
    let busy = false;

    const poll = () => {
      if (!busy) {
        chrome.runtime.sendMessage({ type: 'maya-poll', service });
      }
    };

    chrome.runtime.onMessage.addListener((message) => {
      if (message?.type !== 'maya-command' || !message.command) return;
      if (normalize(message.command.service) !== normalize(service)) return;
      if (busy) return;
      busy = true;
      deliver(message.command, handler).finally(() => {
        busy = false;
      });
    });

    poll();
    setInterval(poll, 800);
  }

  window.MayaBridgeCommon = {
    sleep,
    visible,
    waitFor,
    setInputValue,
    setEditableText,
    normalize,
    exactTextElements,
    findByAriaContains,
    fetchAttachment,
    setFileInput,
    start
  };
})();
