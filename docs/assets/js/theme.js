(() => {
  const html = document.documentElement;
  const btn = document.getElementById('theme-toggle');
  const key = 'cloakmatch-theme';
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const saved = localStorage.getItem(key);
  const initial = saved || (prefersDark ? 'dark' : 'light');
  html.setAttribute('data-theme', initial);
  if (btn) {
    btn.addEventListener('click', () => {
      const cur = html.getAttribute('data-theme') || 'light';
      const next = cur === 'light' ? 'dark' : 'light';
      html.setAttribute('data-theme', next);
      localStorage.setItem(key, next);
    });
  }
})();

