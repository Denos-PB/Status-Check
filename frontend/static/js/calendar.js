document.addEventListener('DOMContentLoaded', () => {
  const statusSelect = document.getElementById('status');
  const deadlineInput = document.getElementById('deadline');
  if (!statusSelect || !deadlineInput) return;

  const syncDeadline = () => {
    if (statusSelect.value === 'ideas_backlog') {
      deadlineInput.value = '';
      deadlineInput.disabled = true;
    } else {
      deadlineInput.disabled = false;
    }
  };

  statusSelect.addEventListener('change', syncDeadline);
  syncDeadline();
});
