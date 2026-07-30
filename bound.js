/* The bound bar: this site's one signature component. Styles in site.css.

   It places a measured effect on a scale whose ends are the smallest effect
   the study could have detected (a minimum detectable effect, or a placebo
   ceiling). A dot resting inside the jaws IS the result on most pages here:
   the study measured something small and states what it could not have seen.
   The bar stays monochrome until an effect clears its bound, which is the one
   place the page chrome is allowed colour.

   Markup is built here rather than repeated per page, so every instance is
   identical and a page only supplies an empty <div class="bound" id="...">.

   Usage:
     drawBound('wcBound', {
       effect: -0.31,          // measured, signed, same unit as bound
       bound: 2.2,             // detectable limit, positive
       unit: 'ct/kWh',
       caption: 'Dot: ... Jaws: ...',
       boundLabel: 'bounded at'  // optional, for placebo ceilings
     });

   Every value must come from a committed result JSON, never a literal: the
   verdict word ("null" or "effect") is derived from the dot's position, so
   the component cannot disagree with the data it was given.
*/
function drawBound(id, opts) {
  const el = document.getElementById(id);
  if (!el) return;
  const { effect, bound, unit = '', caption = '', boundLabel = 'bounded at' } = opts;
  if (bound === null || bound === undefined || !isFinite(bound) || bound <= 0) return;
  if (effect === null || effect === undefined || !isFinite(effect)) return;

  const cleared = Math.abs(effect) >= bound;
  const ratio = Math.max(-1, Math.min(1, effect / bound));
  const sign = n => (n > 0 ? '+' : n < 0 ? '−' : '±');
  const esc = s => String(s).replace(/[&<>]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

  el.style.setProperty('--ratio', ratio.toFixed(3));
  el.classList.toggle('is-effect', cleared);
  // The scale row carries only fixed positions (−bound, 0, +bound); the
  // measured value belongs in the label, because a centred slot would imply
  // the dot sits at zero when it does not.
  el.innerHTML =
    '<p class="bound__label">' +
      '<span class="bound__verdict">' + (cleared ? 'effect' : 'null') + '</span>' +
      '<span>measured ' + sign(effect) + Math.abs(effect) + ' ' + esc(unit) +
        ', ' + esc(boundLabel) + ' ±' + bound + '</span>' +
    '</p>' +
    '<div class="bound__track">' +
      '<span class="bound__jaw bound__jaw--min"></span>' +
      '<span class="bound__jaw bound__jaw--max"></span>' +
      '<span class="bound__dot"></span>' +
    '</div>' +
    '<p class="bound__scale"><span>−' + bound + '</span>' +
      '<span>0</span>' +
      '<span>+' + bound + '</span></p>' +
    (caption ? '<p class="bound__caption">' + esc(caption) + '</p>' : '');
  el.hidden = false;
}
