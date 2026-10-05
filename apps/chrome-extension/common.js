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
    start
  };
})();
