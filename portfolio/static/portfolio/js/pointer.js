/* Pointer effects, for devices that have a real pointer: a soft light that
   follows it across the page, and project cards that tilt toward it. */
(function () {
  'use strict';
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

  const spotlight = document.querySelector('.spotlight');
  let x = 0;
  let y = 0;
  let queued = false;

  function moveSpotlight() {
    queued = false;
    spotlight.style.setProperty('--spot-x', x + 'px');
    spotlight.style.setProperty('--spot-y', y + 'px');
  }

  if (spotlight) {
    window.addEventListener(
      'pointermove',
      (event) => {
        x = event.clientX;
        y = event.clientY;
        if (queued) return;
        queued = true;
        window.requestAnimationFrame(moveSpotlight);
      },
      { passive: true }
    );
  }

  if (!document.documentElement.classList.contains('motion')) return;

  const TILT_PROPERTIES = ['--tilt-x', '--tilt-y', '--glow-x', '--glow-y'];
  document.querySelectorAll('[data-tilt]').forEach((card) => {
    card.addEventListener('pointermove', (event) => {
      const box = card.getBoundingClientRect();
      const across = (event.clientX - box.left) / box.width;
      const down = (event.clientY - box.top) / box.height;
      card.style.setProperty('--tilt-x', ((0.5 - down) * 7).toFixed(2) + 'deg');
      card.style.setProperty('--tilt-y', ((across - 0.5) * 9).toFixed(2) + 'deg');
      card.style.setProperty('--glow-x', (across * 100).toFixed(1) + '%');
      card.style.setProperty('--glow-y', (down * 100).toFixed(1) + '%');
    });
    card.addEventListener('pointerleave', () => {
      TILT_PROPERTIES.forEach((property) => card.style.removeProperty(property));
    });
  });
})();
