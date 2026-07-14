/*
 * DataBossX site enhancement bundle.
 *
 * Everything here is progressive enhancement: the site is fully readable
 * and navigable with JavaScript disabled, and every effect is skipped when
 * the visitor prefers reduced motion. No scroll hijacking — we only observe
 * native scroll position, never override it.
 *
 * Budget note: this is the ONLY client-side JavaScript on the site.
 */

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const finePointer = window.matchMedia('(pointer: fine)');

/* ------------------------------------------------------------------ *
 * 1. Scroll reveals — fade/slide sections in as they enter the view. *
 * ------------------------------------------------------------------ */
function initReveals() {
  const targets = document.querySelectorAll('.reveal');
  if (targets.length === 0) return;

  if (reducedMotion.matches || !('IntersectionObserver' in window)) {
    targets.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      }
    },
    { rootMargin: '0px 0px -10% 0px', threshold: 0.1 }
  );
  targets.forEach((el) => io.observe(el));
}

/* ------------------------------------------------------------------ *
 * 2. Scroll story — activate the pinned visual stage that matches    *
 *    the text block currently in view. Uses position: sticky, so the *
 *    browser keeps full control of scrolling.                        *
 * ------------------------------------------------------------------ */
function initScrollStory() {
  const story = document.querySelector('[data-scroll-story]');
  if (!story) return;

  const steps = story.querySelectorAll('[data-story-step]');
  const scenes = story.querySelectorAll('[data-story-scene]');
  const progress = story.querySelector('[data-story-progress]');
  if (steps.length === 0 || scenes.length === 0) return;

  const activate = (index) => {
    scenes.forEach((scene, i) => scene.classList.toggle('is-active', i === index));
    steps.forEach((step, i) => step.classList.toggle('is-active', i === index));
    if (progress) {
      progress.style.setProperty('--story-progress', String((index + 1) / steps.length));
    }
  };

  if (!('IntersectionObserver' in window)) {
    activate(0);
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activate(Number(entry.target.getAttribute('data-story-step')));
        }
      }
    },
    // A narrow horizontal band around the viewport center decides the
    // active stage, which keeps exactly one stage active at a time.
    { rootMargin: '-45% 0px -45% 0px', threshold: 0 }
  );
  steps.forEach((step) => io.observe(step));
  activate(0);
}

/* ------------------------------------------------------------------ *
 * 3. Command core parallax — a very small pointer-follow tilt on the *
 *    hero visual. Desktop-only (fine pointers), reduced-motion-off,  *
 *    and driven through rAF so it never floods layout.               *
 * ------------------------------------------------------------------ */
function initCommandCoreParallax() {
  const core = document.querySelector('[data-command-core]');
  if (!core || reducedMotion.matches || !finePointer.matches) return;

  let raf = 0;
  let targetX = 0;
  let targetY = 0;

  const apply = () => {
    raf = 0;
    core.style.setProperty('--tilt-x', targetX.toFixed(3));
    core.style.setProperty('--tilt-y', targetY.toFixed(3));
  };

  const hero = core.closest('section') || core;
  hero.addEventListener(
    'pointermove',
    (event) => {
      const rect = core.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      targetX = Math.max(-1, Math.min(1, (event.clientX - cx) / rect.width));
      targetY = Math.max(-1, Math.min(1, (event.clientY - cy) / rect.height));
      if (!raf) raf = requestAnimationFrame(apply);
    },
    { passive: true }
  );
}

/* ------------------------------------------------------------------ *
 * 4. Architecture flow — hovering, focusing, or tapping a node       *
 *    reveals its detail card. Fully keyboard operable; the detail    *
 *    text also exists in the DOM for non-JS visitors.                *
 * ------------------------------------------------------------------ */
function initArchitectureFlow() {
  const flow = document.querySelector('[data-arch-flow]');
  if (!flow) return;

  const nodes = flow.querySelectorAll('[data-arch-node]');
  const details = flow.querySelectorAll('[data-arch-detail]');
  if (nodes.length === 0) return;

  const select = (id) => {
    nodes.forEach((node) => {
      const isActive = node.getAttribute('data-arch-node') === id;
      node.classList.toggle('is-active', isActive);
      node.setAttribute('aria-expanded', String(isActive));
    });
    details.forEach((detail) => {
      detail.classList.toggle('is-active', detail.getAttribute('data-arch-detail') === id);
    });
  };

  nodes.forEach((node) => {
    const id = node.getAttribute('data-arch-node');
    node.addEventListener('click', () => select(id));
    node.addEventListener('focus', () => select(id));
    node.addEventListener('pointerenter', () => select(id));
  });

  select(nodes[0].getAttribute('data-arch-node'));
}

initReveals();
initScrollStory();
initCommandCoreParallax();
initArchitectureFlow();
