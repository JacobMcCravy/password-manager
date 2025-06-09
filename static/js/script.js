document.addEventListener('click', e => {
  if (e.target.matches('[data-showable]')) {
    const input = e.target;
    input.type = input.type === 'password' ? 'text' : 'password';
  }
});