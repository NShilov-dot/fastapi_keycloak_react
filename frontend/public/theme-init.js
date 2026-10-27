// Apply the theme before the bundle loads (no dark-mode flash). A file, not an
// inline script, because the CSP is script-src 'self'. Uses next-themes' 'theme' key.
(function () {
  try {
    var stored = localStorage.getItem('theme')
    var dark =
      stored === 'dark' ||
      ((!stored || stored === 'system') &&
        window.matchMedia('(prefers-color-scheme: dark)').matches)
    var root = document.documentElement
    root.classList.toggle('dark', dark)
    root.style.colorScheme = dark ? 'dark' : 'light'
  } catch (e) {
    /* localStorage/matchMedia unavailable — fall back to light. */
  }
})()
