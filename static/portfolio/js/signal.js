/* The signal on the bus. It runs down the left edge as the page scrolls and
   lights each node it passes. The first time a node lights, its component is
   told to power on ("signal:on"); js/motion.js plays the animation. */
(function () {
  'use strict';
  const schematic = document.querySelector('[data-schematic]');
  if (!schematic) return;

  const bus = schematic.querySelector('.bus');
  const nodes = Array.from(schematic.querySelectorAll('.node'));
  const navLinks = Array.from(document.querySelectorAll('[data-nav]'));
  const powered = new WeakSet();
  let marks = [];
  let top = 0;
  let height = 1;
  let queued = false;

  function measure() {
    const frame = schematic.getBoundingClientRect();
    top = frame.top + window.scrollY;
    height = frame.height;
    marks = nodes.map((node) => ({
      node,
      host: node.closest('[data-stop]'),
      y: node.getBoundingClientRect().top + window.scrollY - top,
    }));
    update();
  }

  function update() {
    queued = false;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const progress = scrollable > 0 ? Math.min(1, window.scrollY / scrollable) : 1;
    // The signal runs ahead of the reader and reaches the end of the bus at the
    // bottom of the page.
    const lead = 0.8 + 0.2 * Math.pow(progress, 4);
    const y = Math.max(0, Math.min(height, window.scrollY + window.innerHeight * lead - top));
    bus.style.setProperty('--signal-y', y + 'px');

    let section = '';
    marks.forEach((mark) => {
      const live = y >= mark.y;
      mark.node.classList.toggle('is-live', live);
      if (!mark.host) return;
      mark.host.classList.toggle('is-live', live);
      if (!live) return;
      if (mark.host.hasAttribute('data-section')) section = mark.host.id;
      if (!powered.has(mark.host)) {
        powered.add(mark.host);
        mark.host.dispatchEvent(new CustomEvent('signal:on', { bubbles: true }));
      }
    });
    navLinks.forEach((link) => {
      link.classList.toggle('is-active', link.getAttribute('href') === '#' + section);
    });
  }

  function requestUpdate() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(update);
  }

  window.addEventListener('scroll', requestUpdate, { passive: true });
  window.addEventListener('resize', measure);
  window.addEventListener('load', measure);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
  // Deferred scripts all run before DOMContentLoaded, so by then js/motion.js
  // is listening for the first "signal:on".
  document.addEventListener('DOMContentLoaded', measure);
})();
