/* Scroll effects. Elements marked data-reveal fade up the first time they come
   into view (those that arrive together, one after another), numbers marked
   data-count count up when they appear, the menu lights the link of the
   section on screen, and the blur at the bottom of the window lifts at the
   end of the page. */
(function () {
  'use strict';
  const root = document.documentElement;
  const observable = 'IntersectionObserver' in window;
  const animated = root.classList.contains('motion') && observable;

  if (animated) root.classList.add('motion-ready');
  else root.classList.remove('motion');

  function countUp(element) {
    const target = parseInt(element.textContent, 10);
    if (!target) return;
    const started = performance.now();
    const duration = 1200;
    element.textContent = '0';
    function step(now) {
      const progress = Math.min(1, (now - started) / duration);
      element.textContent = String(Math.round(target * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  function reveal(element) {
    element.classList.add('is-visible');
    element.querySelectorAll('[data-count]').forEach(countUp);
  }

  if (animated) {
    const revealer = new IntersectionObserver(
      (entries) => {
        entries
          .filter((entry) => entry.isIntersecting)
          .forEach((entry, order) => {
            entry.target.style.setProperty('--reveal-i', String(Math.min(order, 6)));
            reveal(entry.target);
            revealer.unobserve(entry.target);
          });
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.12 }
    );
    document.querySelectorAll('[data-reveal]').forEach((element) => revealer.observe(element));
  }

  if (!observable) return;

  /* The section crossing the middle of the window owns the menu. */
  const links = Array.from(document.querySelectorAll('[data-nav]'));
  if (links.length) {
    const tracker = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const hash = '#' + entry.target.id;
          links.forEach((link) => {
            link.classList.toggle('is-active', link.getAttribute('href') === hash);
          });
        });
      },
      { rootMargin: '-45% 0px -50% 0px' }
    );
    document.querySelectorAll('[data-section]').forEach((section) => tracker.observe(section));
  }

  const fade = document.querySelector('[data-page-fade]');
  const end = document.querySelector('[data-page-end]');
  if (fade && end) {
    new IntersectionObserver((entries) => {
      fade.classList.toggle('is-hidden', entries[0].isIntersecting);
    }).observe(end);
  }
})();
