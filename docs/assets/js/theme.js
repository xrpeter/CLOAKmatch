(function() {
  var KEY = 'jtd-theme';
  var root = document.documentElement;
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  var saved = localStorage.getItem(KEY);
  var theme = saved || (prefersDark ? 'dark' : 'light');
  root.setAttribute('data-theme', theme);

  function addToggle() {
    var header = document.querySelector('.site-header .site-title') || document.querySelector('.site-header');
    if (!header) return;
    var btn = document.createElement('button');
    btn.id = 'theme-toggle';
    btn.type = 'button';
    btn.style.marginLeft = '0.75rem';
    btn.style.padding = '4px 8px';
    btn.style.border = '1px solid rgba(127,127,127,0.3)';
    btn.style.borderRadius = '6px';
    btn.style.background = 'transparent';
    btn.style.cursor = 'pointer';
    btn.textContent = theme === 'dark' ? 'Light' : 'Dark';
    btn.addEventListener('click', function(){
      theme = (root.getAttribute('data-theme') === 'dark') ? 'light' : 'dark';
      root.setAttribute('data-theme', theme);
      localStorage.setItem(KEY, theme);
      btn.textContent = theme === 'dark' ? 'Light' : 'Dark';
    });
    header.appendChild(btn);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addToggle);
  } else {
    addToggle();
  }
})();

