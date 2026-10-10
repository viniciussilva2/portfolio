/* Power-on animations. Each component stays dark until the bus signal reaches
   its node (js/signal.js), then its text decodes, its parts slide in from the
   bus side and its technology tokens light up one by one. */
(function () {
  'use strict';
  const root = document.documentElement;
  if (!root.classList.contains('motion')) return;
  if (!window.gsap) {
    root.classList.remove('motion');
    return;
  }
  root.classList.add('motion-ready');

  const gsap = window.gsap;
  const GLYPHS = '01<>/[]{}=+#';

  /* Elements that belong to this component and not to one nested inside it. */
  function own(host, selector) {
    return Array.from(host.querySelectorAll(selector)).filter(
      (element) => element.closest('[data-stop]') === host
    );
  }

  function randomGlyphs(count) {
    let glyphs = '';
    for (let i = 0; i < count; i++) glyphs += GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
    return glyphs;
  }

  /* Types the text in behind two raw glyphs. The untyped rest stays in place,
     invisible, so nothing reflows; screen readers get the plain text. */
  function decode(element, duration) {
    const text = element.textContent;
    const letters = Array.from(text);
    const state = { typed: 0 };
    let done, edge, rest;
    return gsap.to(state, {
      typed: letters.length,
      duration: duration || Math.min(1.1, 0.35 + letters.length * 0.025),
      ease: 'none',
      onStart() {
        const spoken = document.createElement('span');
        spoken.className = 'visually-hidden';
        spoken.textContent = text;
        const visual = document.createElement('span');
        visual.setAttribute('aria-hidden', 'true');
        done = document.createElement('span');
        edge = document.createElement('span');
        edge.className = 'decode__edge';
        rest = document.createElement('span');
        rest.className = 'decode__rest';
        rest.textContent = text;
        visual.append(done, edge, rest);
        element.replaceChildren(spoken, visual);
        element.style.opacity = 1;
      },
      onUpdate() {
        const typed = Math.floor(state.typed);
        const raw = Math.min(2, letters.length - typed);
        done.textContent = letters.slice(0, typed).join('');
        edge.textContent = randomGlyphs(raw);
        rest.textContent = letters.slice(typed + raw).join('');
      },
      onComplete() {
        element.textContent = text;
      },
    });
  }

  function countUp(element) {
    const target = parseInt(element.textContent, 10);
    if (!target) return null;
    const state = { value: 0 };
    return gsap.to(state, {
      value: target,
      duration: 1.1,
      ease: 'power2.out',
      onUpdate() {
        element.textContent = Math.round(state.value);
      },
    });
  }

  function slideIn(timeline, parts, at, stagger) {
    if (!parts.length) return;
    timeline.fromTo(
      parts,
      { opacity: 0, x: -18 },
      { opacity: 1, x: 0, duration: 0.7, ease: 'power3.out', stagger: stagger },
      at
    );
  }

  function lightUp(timeline, tokens, at) {
    if (!tokens.length) return;
    timeline.fromTo(
      tokens,
      { opacity: 0, backgroundColor: 'rgba(127, 212, 255, 0.55)' },
      {
        opacity: 1,
        backgroundColor: 'rgba(45, 123, 255, 0.06)',
        duration: 0.45,
        ease: 'power1.out',
        stagger: 0.05,
      },
      at
    );
  }

  /* The page-load sequence: name, then the rest of the hero, then the spec sheet. */
  function bootHero(hero) {
    const timeline = gsap.timeline();
    const nameLines = Array.from(hero.querySelectorAll('.hero__name [data-decode]'));
    const specValues = Array.from(hero.querySelectorAll('.spec [data-decode]'));
    nameLines.forEach((line, index) => timeline.add(decode(line, 0.9), 0.2 + index * 0.3));
    slideIn(timeline, own(hero, '[data-part]'), 0.9, 0.12);
    specValues.forEach((value, index) => timeline.add(decode(value), 1.5 + index * 0.15));
    own(hero, '[data-count]').forEach((counter) => {
      const tween = countUp(counter);
      if (tween) timeline.add(tween, 1.6);
    });
    lightUp(timeline, own(hero, '[data-led]'), 2.1);
  }

  function powerOn(host) {
    if (host.hasAttribute('data-hero')) {
      bootHero(host);
      return;
    }
    const timeline = gsap.timeline();
    own(host, '[data-decode]').forEach((element, index) => {
      timeline.add(decode(element), 0.1 + index * 0.08);
    });
    slideIn(timeline, own(host, '[data-part]'), 0.15, 0.07);
    lightUp(timeline, own(host, '[data-led]'), 0.35);
  }

  document.addEventListener('signal:on', (event) => powerOn(event.target));
})();
