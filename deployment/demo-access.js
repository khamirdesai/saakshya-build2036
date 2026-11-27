// Deployment helper only. The original form authenticates the issued token.
const button = document.getElementById('public-demo-access');
button?.addEventListener('click', async () => {
  const message = document.getElementById('public-demo-status');
  button.disabled = true;
  try {
    const role = document.getElementById('public-demo-role').value;
    const response = await fetch('/submission/demo-session?role=' + encodeURIComponent(role), {method:'POST'});
    if (!response.ok) throw new Error('Demo access could not be issued. Try again.');
    const data = await response.json();
    for (const [id,value] of [['gate-officer',data.user_id],['gate-token',data.token],['gate-case',data.case_id],['gate-purpose',data.purpose]]) {
      document.getElementById(id).value = value;
    }
    message.textContent = 'Demo access is ready. Select Enter the workspace to sign in through the original server gate.';
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
