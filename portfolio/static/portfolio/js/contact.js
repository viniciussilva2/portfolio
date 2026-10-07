/* Sends the contact form without leaving the page. Without this script the
   form still works: it posts normally and the server answers with a page.
   The two texts this script shows on its own come translated from the form's
   data attributes. */
(function () {
  'use strict';
  const form = document.querySelector('[data-contact-form]');
  if (!form || !window.fetch) return;

  const status = form.querySelector('[data-form-status]');
  const button = form.querySelector('[data-submit]');
  const idleLabel = button.textContent;

  function showStatus(message, isError) {
    status.textContent = message || '';
    status.classList.toggle('form__status--error', Boolean(isError));
  }

  function showFieldErrors(errors) {
    let firstInvalid = null;
    form.querySelectorAll('[data-error-for]').forEach((slot) => {
      const field = form.elements[slot.dataset.errorFor];
      const messages = errors[slot.dataset.errorFor];
      slot.textContent = messages ? messages[0] : '';
      if (!field) return;
      if (messages) {
        field.setAttribute('aria-invalid', 'true');
        firstInvalid = firstInvalid || field;
      } else {
        field.removeAttribute('aria-invalid');
      }
    });
    if (firstInvalid) firstInvalid.focus();
  }

  /* The server hands out a new token when the old one expired. */
  function replaceToken(token) {
    const input = form.elements.token;
    input.value = token;
    input.setAttribute('value', token);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    button.textContent = form.dataset.sendingLabel;
    showStatus('');
    showFieldErrors({});
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      });
      const result = await response.json();
      if (result.ok) {
        form.reset();
        showStatus(result.message);
      } else {
        if (result.token) replaceToken(result.token);
        showFieldErrors(result.errors || {});
        showStatus(result.error, true);
      }
    } catch (error) {
      showStatus(form.dataset.networkError, true);
    } finally {
      button.disabled = false;
      button.textContent = idleLabel;
    }
  });
})();
