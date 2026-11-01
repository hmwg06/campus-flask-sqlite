const toggle = document.querySelector('.menu-toggle');
const sidebar = document.querySelector('.sidebar');
if (toggle && sidebar) {
  toggle.addEventListener('click', () => {
    const open = sidebar.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      sidebar.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
}
