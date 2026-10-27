/* Cards marked data-glow brighten where the pointer is (css/base.css draws
   the light). Only for devices with a real pointer. */
(function () {
  'use strict';
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

  document.querySelectorAll('[data-glow]').forEach((card) => {
    card.addEventListener('pointermove', (event) => {
      const box = card.getBoundingClientRect();
      card.style.setProperty('--glow-x', (((event.clientX - box.left) / box.width) * 100).toFixed(1) + '%');
      card.style.setProperty('--glow-y', (((event.clientY - box.top) / box.height) * 100).toFixed(1) + '%');
    });
  });
})();
