/* Chart.js defaults for this site, so figures use the page's typography and
   greys instead of Chart.js's own. Load it in <head> immediately after the
   Chart.js tag and WITHOUT defer: the pages build their charts from an inline
   script at the end of <body>, which runs before any deferred script, so a
   deferred theme would apply too late to have any effect.

   Colours here are the chrome tokens from site.css (--muted, --line, --ink).
   Series colours stay in the pages, because they are data and are shared with
   the matplotlib figures. Prose faces match site.css; axis ticks are mono so
   numbers line up column to column the way they do in the tables.

   Note: the matplotlib figures the Python scripts write are deliberately left
   on their default face. Pinning IBM Plex there would need the font installed
   on every machine including the CI runner, and a missing family degrades to
   warnings plus a silent fallback. */
(function () {
  if (!window.Chart) return;

  var SANS = "'IBM Plex Sans', -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif";
  var MONO = "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
  var INK = '#16191c', MUTED = '#5b666c', LINE = '#dfe4e6';

  Chart.defaults.font.family = SANS;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = MUTED;

  Chart.defaults.plugins.title.color = INK;
  Chart.defaults.plugins.title.font = { family: SANS, size: 13, weight: '600' };
  Chart.defaults.plugins.title.padding = { top: 2, bottom: 12 };

  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.legend.labels.boxHeight = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = false;
  Chart.defaults.plugins.legend.labels.font = { family: SANS, size: 11.5 };

  Chart.defaults.plugins.tooltip.titleFont = { family: MONO, size: 11.5 };
  Chart.defaults.plugins.tooltip.bodyFont = { family: SANS, size: 11.5 };
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(22,25,28,.93)';
  Chart.defaults.plugins.tooltip.padding = 8;
  Chart.defaults.plugins.tooltip.cornerRadius = 3;

  Chart.defaults.scale.grid.color = LINE;
  Chart.defaults.scale.grid.tickColor = LINE;
  Chart.defaults.scale.border = Chart.defaults.scale.border || {};
  Chart.defaults.scale.border.color = LINE;
  Chart.defaults.scale.ticks.color = MUTED;
  Chart.defaults.scale.ticks.font = { family: MONO, size: 10.5 };
  Chart.defaults.scale.title.color = MUTED;
  Chart.defaults.scale.title.font = { family: SANS, size: 11.5, weight: '400' };
})();
