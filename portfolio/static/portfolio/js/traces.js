/* Hero background: circuit-board traces with data pulses travelling along
   them. Traces near the pointer heat up and fire more pulses. Without motion
   (reduced-motion preference) the traces are drawn once and stay still. */
(function () {
  'use strict';
  const canvas = document.querySelector('[data-traces]');
  if (!canvas || !canvas.getContext) return;

  const context = canvas.getContext('2d');
  const hero = canvas.parentElement;
  const animated = document.documentElement.classList.contains('motion');

  const CELL = 28; // same pitch as --grid in css/tokens.css
  const DIRECTIONS = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
  const INTRO_SECONDS = 1.8;
  const POINTER_REACH = 150;
  const MAX_PULSES = 90;
  const BLUE = '45, 123, 255';
  const ICE = '127, 212, 255';

  let width = 0;
  let height = 0;
  let ratio = 1;
  let traces = [];
  let pulses = [];
  let flashes = [];
  let layer = null; // every trace fully drawn, reused each frame once the intro is over
  let startedAt = 0;
  let lastFrame = 0;
  let spawnDebt = 0;
  let frameId = 0;
  let onScreen = true;
  let introDone = !animated;
  const pointer = { x: -9999, y: -9999 };

  function between(min, max) {
    return min + Math.random() * (max - min);
  }

  /* Grows one trace on the grid: straight runs joined by 45-degree turns, never
     touching or crossing a trace that is already there. */
  function grow(columns, rows, used) {
    let column = Math.floor(between(1, columns));
    let row = Math.floor(between(1, rows));
    // Sparser on the left, where the text is.
    if (Math.random() > 0.25 + 0.75 * (column / columns)) return null;
    if (used.has(column + ':' + row)) return null;

    const taken = [column + ':' + row];
    const corners = [[column, row]];
    let direction = Math.floor(Math.random() * 4) * 2;
    const runs = Math.floor(between(2, 6));
    for (let run = 0; run < runs; run++) {
      const steps = Math.floor(between(2, 9));
      let moved = 0;
      for (let step = 0; step < steps; step++) {
        const nextColumn = column + DIRECTIONS[direction][0];
        const nextRow = row + DIRECTIONS[direction][1];
        const cell = nextColumn + ':' + nextRow;
        // A diagonal step also claims the midpoint, so two diagonals cannot cross.
        const crossing = 'x' + (column + nextColumn) + ':' + (row + nextRow);
        if (nextColumn < 1 || nextRow < 1 || nextColumn >= columns || nextRow >= rows) break;
        if (used.has(cell) || used.has(crossing) || taken.includes(cell)) break;
        taken.push(cell);
        if (direction % 2) taken.push(crossing);
        column = nextColumn;
        row = nextRow;
        moved++;
      }
      if (moved) corners.push([column, row]);
      direction = (direction + (Math.random() < 0.5 ? 1 : 7)) % 8;
    }
    if (corners.length < 3) return null;
    taken.forEach((cell) => used.add(cell));

    const points = corners.map((corner) => ({ x: corner[0] * CELL, y: corner[1] * CELL }));
    const lengths = [0];
    for (let i = 1; i < points.length; i++) {
      const previous = points[i - 1];
      lengths.push(lengths[i - 1] + Math.hypot(points[i].x - previous.x, points[i].y - previous.y));
    }
    return {
      points,
      lengths,
      total: lengths[lengths.length - 1],
      minX: Math.min(...points.map((point) => point.x)),
      maxX: Math.max(...points.map((point) => point.x)),
      minY: Math.min(...points.map((point) => point.y)),
      maxY: Math.max(...points.map((point) => point.y)),
      delay: Math.random() * (INTRO_SECONDS - 0.8),
      heat: 0,
    };
  }

  function pointAt(trace, distance) {
    const along = Math.max(0, Math.min(trace.total, distance));
    let i = 1;
    while (i < trace.lengths.length - 1 && trace.lengths[i] < along) i++;
    const from = trace.points[i - 1];
    const to = trace.points[i];
    const span = trace.lengths[i] - trace.lengths[i - 1];
    const fraction = span ? (along - trace.lengths[i - 1]) / span : 0;
    return { x: from.x + (to.x - from.x) * fraction, y: from.y + (to.y - from.y) * fraction };
  }

  /* Traces the stretch of a trace between two distances along it. */
  function stretch(target, trace, from, to) {
    const start = pointAt(trace, from);
    const end = pointAt(trace, to);
    target.beginPath();
    target.moveTo(start.x, start.y);
    for (let i = 1; i < trace.points.length - 1; i++) {
      if (trace.lengths[i] > from && trace.lengths[i] < to) {
        target.lineTo(trace.points[i].x, trace.points[i].y);
      }
    }
    target.lineTo(end.x, end.y);
  }

  function drawPad(target, point, alpha) {
    target.beginPath();
    target.arc(point.x, point.y, 2.5, 0, Math.PI * 2);
    target.fillStyle = '#000';
    target.fill();
    target.lineWidth = 1;
    target.strokeStyle = 'rgba(' + ICE + ', ' + alpha + ')';
    target.stroke();
  }

  function drawTrace(target, trace, upTo) {
    if (upTo <= 0) return;
    target.lineWidth = 1;
    target.strokeStyle = 'rgba(' + BLUE + ', 0.34)';
    stretch(target, trace, 0, upTo);
    target.stroke();
    drawPad(target, trace.points[0], 0.6);
    if (upTo >= trace.total) drawPad(target, trace.points[trace.points.length - 1], 0.6);
  }

  function build() {
    const box = canvas.getBoundingClientRect();
    width = box.width;
    height = box.height;
    ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);

    const columns = Math.ceil(width / CELL);
    const rows = Math.ceil(height / CELL);
    const wanted = Math.round((columns * rows) / 26);
    const used = new Set();
    traces = [];
    for (let attempt = 0; traces.length < wanted && attempt < wanted * 20; attempt++) {
      const trace = grow(columns, rows, used);
      if (trace) traces.push(trace);
    }
    pulses = [];
    flashes = [];

    layer = document.createElement('canvas');
    layer.width = canvas.width;
    layer.height = canvas.height;
    const layerContext = layer.getContext('2d');
    layerContext.setTransform(ratio, 0, 0, ratio, 0, 0);
    traces.forEach((trace) => drawTrace(layerContext, trace, trace.total));
  }

  function drawStill() {
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.drawImage(layer, 0, 0, width, height);
  }

  function spawn(trace) {
    pulses.push({
      trace,
      travelled: 0,
      speed: between(140, 320),
      tail: between(40, 90),
      reverse: Math.random() < 0.5,
      landed: false,
    });
    if (pulses.length > MAX_PULSES) pulses.shift();
  }

  function nearPointer(trace) {
    if (
      pointer.x < trace.minX - POINTER_REACH ||
      pointer.x > trace.maxX + POINTER_REACH ||
      pointer.y < trace.minY - POINTER_REACH ||
      pointer.y > trace.maxY + POINTER_REACH
    ) {
      return false;
    }
    for (let along = 0; along <= trace.total; along += CELL) {
      const point = pointAt(trace, along);
      if (Math.hypot(point.x - pointer.x, point.y - pointer.y) < POINTER_REACH) return true;
    }
    return false;
  }

  function drawPulse(pulse, elapsed) {
    const trace = pulse.trace;
    pulse.travelled += pulse.speed * elapsed;
    const head = Math.min(pulse.travelled, trace.total);
    const tail = Math.max(0, pulse.travelled - pulse.tail);
    // Distances are measured from the end the pulse started at.
    const at = (distance) => (pulse.reverse ? trace.total - distance : distance);
    const low = Math.min(at(head), at(tail));
    const high = Math.max(at(head), at(tail));
    if (high > low) {
      context.lineWidth = 3;
      context.strokeStyle = 'rgba(' + BLUE + ', 0.4)';
      stretch(context, trace, low, high);
      context.stroke();
      context.lineWidth = 1.25;
      context.strokeStyle = 'rgba(' + ICE + ', 0.95)';
      stretch(context, trace, low, high);
      context.stroke();
    }
    if (pulse.travelled < trace.total) {
      const tip = pointAt(trace, at(head));
      context.fillStyle = '#fff';
      context.fillRect(tip.x - 1.5, tip.y - 1.5, 3, 3);
    } else if (!pulse.landed) {
      pulse.landed = true;
      flashes.push({ point: pointAt(trace, at(trace.total)), age: 0 });
    }
    return pulse.travelled < trace.total + pulse.tail;
  }

  function drawFlash(flash, elapsed) {
    flash.age += elapsed;
    const progress = flash.age / 0.55;
    if (progress >= 1) return false;
    context.beginPath();
    context.arc(flash.point.x, flash.point.y, 3 + progress * 12, 0, Math.PI * 2);
    context.lineWidth = 1;
    context.strokeStyle = 'rgba(' + ICE + ', ' + (1 - progress) * 0.8 + ')';
    context.stroke();
    return true;
  }

  function frame(now) {
    frameId = 0;
    const elapsed = Math.min((now - lastFrame) / 1000, 0.05);
    lastFrame = now;
    const age = (now - startedAt) / 1000;
    if (age >= INTRO_SECONDS) introDone = true;

    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.lineCap = 'round';
    context.lineJoin = 'round';

    if (introDone) {
      context.drawImage(layer, 0, 0, width, height);
    } else {
      // The board draws itself: each trace grows from its first pad.
      traces.forEach((trace) => {
        const progress = Math.max(0, Math.min(1, (age - trace.delay) / 0.8));
        drawTrace(context, trace, trace.total * (1 - Math.pow(1 - progress, 3)));
      });
    }

    if (introDone) {
      traces.forEach((trace) => {
        const near = nearPointer(trace);
        trace.heat = near
          ? Math.min(1, trace.heat + elapsed * 5)
          : Math.max(0, trace.heat - elapsed * 1.4);
        if (trace.heat < 0.02) return;
        context.lineWidth = 1.25;
        context.strokeStyle = 'rgba(' + ICE + ', ' + trace.heat * 0.7 + ')';
        stretch(context, trace, 0, trace.total);
        context.stroke();
        if (near && Math.random() < elapsed * 1.6) spawn(trace);
      });

      spawnDebt += (elapsed * traces.length) / 22;
      while (spawnDebt >= 1 && traces.length) {
        spawnDebt -= 1;
        spawn(traces[Math.floor(Math.random() * traces.length)]);
      }
    }

    pulses = pulses.filter((pulse) => drawPulse(pulse, elapsed));
    flashes = flashes.filter((flash) => drawFlash(flash, elapsed));
    schedule();
  }

  function schedule() {
    if (frameId || !animated || !onScreen || document.hidden) return;
    frameId = window.requestAnimationFrame(frame);
  }

  function start() {
    build();
    if (!animated) {
      drawStill();
      return;
    }
    startedAt = lastFrame = performance.now();
    schedule();
  }

  let resizeTimer = 0;
  window.addEventListener('resize', () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      const box = canvas.getBoundingClientRect();
      // Mobile browsers resize constantly as their toolbars slide; only a real
      // change of layout is worth a new board.
      if (Math.abs(box.width - width) < 2 && Math.abs(box.height - height) < 80) return;
      build();
      if (animated) schedule();
      else drawStill();
    }, 180);
  });

  hero.addEventListener(
    'pointermove',
    (event) => {
      const box = canvas.getBoundingClientRect();
      pointer.x = event.clientX - box.left;
      pointer.y = event.clientY - box.top;
    },
    { passive: true }
  );
  hero.addEventListener('pointerleave', () => {
    pointer.x = pointer.y = -9999;
  });

  if ('IntersectionObserver' in window) {
    new IntersectionObserver((entries) => {
      onScreen = entries[0].isIntersecting;
      schedule();
    }).observe(canvas);
  }
  document.addEventListener('visibilitychange', schedule);

  start();
})();
