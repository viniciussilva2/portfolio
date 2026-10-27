/* Section menu on small screens: folded into a panel under the navigation
   pill, opened by a button. Without this script the button is not shown and
   the call-to-action stays as the one way to the contact section. */
(function () {
  'use strict';
  const toggle = document.querySelector('[data-menu-toggle]');
  const menu = document.getElementById('menu');
  if (!toggle || !menu) return;

  function setOpen(open) {
    menu.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
  }

  toggle.addEventListener('click', () => setOpen(!menu.classList.contains('is-open')));
  menu.addEventListener('click', (event) => {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('click', (event) => {
    if (!event.target.closest('.nav')) setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !menu.classList.contains('is-open')) return;
    setOpen(false);
    toggle.focus();
  });
})();
