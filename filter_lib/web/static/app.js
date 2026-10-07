// Progressive enhancement for the design page. Without this script the download
// buttons still work as plain form posts and the page stays fully usable.
(function () {
  "use strict";

  function statusLine() {
    return document.getElementById("download-status");
  }

  function setStatus(text, isError) {
    var line = statusLine();
    if (!line) return;
    line.textContent = text;
    line.classList.toggle("is-error", Boolean(isError));
  }

  function filenameFrom(response, fallback) {
    var header = response.headers.get("Content-Disposition") || "";
    var match = /filename="([^"]+)"/.exec(header);
    return match ? match[1] : fallback;
  }

  function saveBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  // Fetch the export so a failure is shown next to the buttons instead of
  // replacing the page with an error document.
  async function download(button) {
    var form = document.getElementById(button.getAttribute("form"));
    if (!form || button.disabled) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    setStatus("Preparing " + button.textContent.trim() + "…", false);
    try {
      var response = await fetch(button.formAction, { method: "POST", body: new FormData(form) });
      if (!response.ok) {
        var problem = await response.json().catch(function () { return {}; });
        throw new Error(problem.error || "The download failed (HTTP " + response.status + ").");
      }
      var filename = filenameFrom(response, "filter-export.txt");
      saveBlob(await response.blob(), filename);
      setStatus("Saved " + filename, false);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  }

  async function copyOutput(button) {
    var source = document.getElementById(button.dataset.copy);
    if (!source || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(source.textContent);
      button.textContent = "Copied";
    } catch (error) {
      button.textContent = "Copy failed";
    }
    setTimeout(function () { button.textContent = "Copy"; }, 1600);
  }

  document.addEventListener("click", function (event) {
    var downloadButton = event.target.closest("[data-download]");
    if (downloadButton) {
      event.preventDefault();
      download(downloadButton);
      return;
    }
    var copyButton = event.target.closest("[data-copy]");
    if (copyButton) copyOutput(copyButton);
  });
})();
