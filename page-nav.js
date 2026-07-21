// Shared page navigation: the section menu and the back-to-top button.
//
// To use on a page: link page-nav.css, put an empty
//   <nav id="toc" aria-label="On this page"></nav>
// where the menu should sit in the flow on narrow screens (on wide screens it
// is fixed beside the text, so the position only matters below 1180px), and
// load this file with <script src="page-nav.js" defer></script>.
//
// The menu is built from every `section[id] > h2` on the page, so it cannot
// drift from the headings: add a section with an id and it appears. Sections
// without an id are skipped (there is no anchor to link to). Pages whose
// sections are revealed after a fetch should call `window.syncPageNav()` once
// the data has rendered, so entries appear with their sections.
//
// A page without <nav id="toc"> gets neither feature, which is how a page
// opts out.

(function () {
  const nav = document.getElementById('toc');
  if (!nav) return;

  nav.innerHTML = '<details id="tocDet" open>' +
    '<summary>On this page</summary><ol></ol></details>';
  const ol = nav.querySelector('ol');
  const det = nav.querySelector('#tocDet');

  const items = [...document.querySelectorAll('section[id] > h2')].map(h => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '#' + h.parentElement.id;
    a.textContent = h.textContent;
    li.appendChild(a);
    ol.appendChild(li);
    return { sec: h.parentElement, li, a };
  });

  const toTop = document.createElement('button');
  toTop.id = 'toTop';
  toTop.type = 'button';
  toTop.title = 'Back to top';
  toTop.innerHTML = '&uarr; top';
  document.body.appendChild(toTop);

  // One scroll handler for both features: it marks the section being read and
  // shows the button once the page is scrolled. Entries for sections that are
  // hidden (revealed only when their data loads) hide with them.
  const sync = () => {
    let active = null;
    for (const it of items) {
      const hidden = it.sec.offsetParent === null;
      it.li.style.display = hidden ? 'none' : '';
      if (!hidden && it.sec.getBoundingClientRect().top <= 120) active = it;
    }
    for (const it of items) it.a.classList.toggle('active', it === active);
    toTop.classList.toggle('show', scrollY > 600);
  };
  addEventListener('scroll', sync, { passive: true });
  addEventListener('resize', sync);
  sync();

  // Wide viewports: always expanded, beside the text. Narrow: collapsed by
  // default, and collapses again after a jump so it stays out of the way.
  const wide = matchMedia('(min-width:1181px)');
  const fit = () => { det.open = wide.matches; };
  wide.addEventListener('change', fit);
  fit();
  ol.addEventListener('click', e => {
    if (e.target.tagName === 'A' && !wide.matches) det.open = false;
  });

  toTop.addEventListener('click', () => scrollTo({ top: 0,
    behavior: matchMedia('(prefers-reduced-motion:reduce)').matches
      ? 'auto' : 'smooth' }));

  window.syncPageNav = sync;
})();
