// Shared JavaScript for the linked Dublin Traffic AI pages.
// Keeps the simulation clock moving and highlights the active navigation link.
(function () {
  function pad(n) { return String(n).padStart(2, '0'); }

  function updateSimulationClocks() {
    const now = new Date();
    const value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    document.querySelectorAll('#simulation-clock, [data-simulation-clock]').forEach((el) => {
      el.textContent = value;
    });
  }

  function normalizePath(path) {
    const last = path.split('/').pop() || 'index.html';
    return last === '' ? 'index.html' : last;
  }

  function highlightActiveNav() {
    const current = normalizePath(window.location.pathname);
    document.querySelectorAll('nav a[href]').forEach((link) => {
      const href = normalizePath(link.getAttribute('href') || '');
      if (href === current || (current === '' && href === 'index.html')) {
        link.setAttribute('aria-current', 'page');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    updateSimulationClocks();
    setInterval(updateSimulationClocks, 1000);
    highlightActiveNav();
  });
})();
