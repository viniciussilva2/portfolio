/* Runs in <head>, before first paint: decides whether the page animates.
   "motion" hides components until their animation plays, so it is only set
   when the visitor has not asked for reduced motion, and it is taken back if
   the animation scripts never start. */
(function (root) {
  'use strict';
  root.classList.add('js');
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  root.classList.add('motion');
  window.setTimeout(function () {
    if (!root.classList.contains('motion-ready')) root.classList.remove('motion');
  }, 4000);
})(document.documentElement);
