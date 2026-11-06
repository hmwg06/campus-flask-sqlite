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

document.querySelectorAll('form[data-ai-request]').forEach(form => {
  form.addEventListener('submit', event => {
    if (form.dataset.busy === 'true') {
      event.preventDefault();
      return;
    }
    form.dataset.busy = 'true';
    form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; });
    const status = form.querySelector('.ai-request-status');
    if (status) status.hidden = false;
  });
});

window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[data-ai-request][data-busy="true"]').forEach(form => {
    delete form.dataset.busy;
    form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = false; });
    const status = form.querySelector('.ai-request-status');
    if (status) status.hidden = true;
  });
});
