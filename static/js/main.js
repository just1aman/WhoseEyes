// Whose Eyes? — shared JS
// Most page logic lives in inline <script> blocks in templates.
// This file handles utilities shared across all pages.

// Auto-uppercase room code inputs
document.addEventListener('DOMContentLoaded', function () {
  var codeInput = document.getElementById('join-code');
  if (codeInput) {
    codeInput.addEventListener('input', function () {
      var pos = this.selectionStart;
      this.value = this.value.toUpperCase();
      this.setSelectionRange(pos, pos);
    });
  }
});
