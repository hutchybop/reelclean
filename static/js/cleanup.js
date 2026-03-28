"use strict";

(function initCleanupSelection() {
  function setAllChecks(checked) {
    var checks = document.querySelectorAll(".cleanup-check");
    checks.forEach(function onEach(input) {
      input.checked = checked;
    });
  }

  var checkAllButton = document.getElementById("check-all-btn");
  var uncheckAllButton = document.getElementById("uncheck-all-btn");

  if (checkAllButton) {
    checkAllButton.addEventListener("click", function onCheckAll() {
      setAllChecks(true);
    });
  }

  if (uncheckAllButton) {
    uncheckAllButton.addEventListener("click", function onUncheckAll() {
      setAllChecks(false);
    });
  }
})();
