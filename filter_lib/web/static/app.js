// Progressive enhancement for the design page. Without this script every control
// stays enabled (the server refuses an option that cannot apply, with the reason),
// the download buttons still post the inputs of the result shown, and the page stays
// fully usable.
(function () {
  "use strict";

  // Options that cannot apply ------------------------------------------------------
  // The form carries the shared rule's answer for every combination of the five
  // choices below (filter_lib/web/option_states.py); this only looks it up.

  function checkedValue(form, name) {
    var input = form.querySelector('input[name="' + name + '"]:checked');
    return input ? input.value : "";
  }

  function isTicked(form, name) {
    var input = form.querySelector('input[type="checkbox"][name="' + name + '"]');
    return Boolean(input && input.checked);
  }

  function stateKey(form) {
    return [
      checkedValue(form, "output_format") || "table",
      checkedValue(form, "eseries") === "none" ? "1" : "0",
      isTicked(form, "raw") ? "1" : "0",
      isTicked(form, "sim_build") ? "1" : "0",
      checkedValue(form, "toroids") === "none" ? "1" : "0",
    ].join("|");
  }

  // A disabled control's value is not submitted, so the result shown does not use it.
  // Its visible value still goes along as "visible.<name>": the result keeps it with
  // its inputs, and each download uses it where it applies to that document
  // (filter_lib/web/download_inputs.py), never a substituted default.
  function mirrorVisibleValues(form) {
    form.querySelectorAll("[data-mirror]").forEach(function (mirror) { mirror.remove(); });
    form.querySelectorAll("[data-option]").forEach(function (control) {
      if (!control.disabled) return;
      if ((control.type === "radio" || control.type === "checkbox") && !control.checked) return;
      if (control.type === "text" && !control.value.trim()) return;
      var mirror = document.createElement("input");
      mirror.type = "hidden";
      mirror.name = "visible." + control.name;
      mirror.value = control.value;
      mirror.setAttribute("data-mirror", "");
      form.appendChild(mirror);
    });
  }

  // A disabled control leaves the tab order, so its reason is also announced: the
  // form's polite status line says why each newly unavailable option is unavailable.
  // Each reason stays tied to its control by aria-describedby. A fresh form says nothing.
  var unavailableBefore = new WeakMap();

  function announceUnavailable(form, table, state) {
    var previous = unavailableBefore.get(form);
    unavailableBefore.set(form, Object.keys(state));
    var status = form.querySelector("[data-option-status]");
    if (!status || previous === undefined) return;
    var reasons = [];
    Object.keys(state).forEach(function (option) {
      var reason = table.reasons[state[option]];
      if (previous.indexOf(option) === -1 && reasons.indexOf(reason) === -1) reasons.push(reason);
    });
    status.textContent = reasons.join(" ");
  }

  function refreshOptions(form) {
    if (!form || !form.dataset.optionStates) return;
    var table = JSON.parse(form.dataset.optionStates);
    var state = table.states[stateKey(form)] || {};
    form.querySelectorAll("[data-option]").forEach(function (control) {
      // A disabled control is not submitted, so the server uses the CLI default,
      // as when the CLI flag is left out.
      control.disabled = state[control.dataset.option] !== undefined;
    });
    mirrorVisibleValues(form);
    form.querySelectorAll("[data-reason-for]").forEach(function (line) {
      var index = state[line.dataset.reasonFor];
      line.textContent = index === undefined ? "" : table.reasons[index];
      line.hidden = index === undefined;
    });
    announceUnavailable(form, table, state);
  }

  // Inputs changed since the result ------------------------------------------------

  function fields(form) {
    // Last value wins for a repeated name, as on the server.
    var values = {};
    new FormData(form).forEach(function (value, name) {
      if (typeof value === "string") values[name] = value;
    });
    return values;
  }

  function sameFields(a, b) {
    var names = Object.keys(a);
    if (names.length !== Object.keys(b).length) return false;
    return names.every(function (name) { return b[name] === a[name]; });
  }

  function refreshStale() {
    var form = document.getElementById("design-form");
    var shown = document.getElementById("result-inputs");
    var notice = document.getElementById("stale-notice");
    if (!form || !shown || !notice) return;
    notice.hidden = sameFields(fields(form), fields(shown));
  }

  function refreshAll() {
    refreshOptions(document.getElementById("design-form"));
    refreshStale();
  }

  // Downloads ----------------------------------------------------------------------

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
  // replacing the page with an error document. The button's form holds the
  // inputs of the result shown.
  async function download(button) {
    var form = button.form;
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
      setStatus("Downloaded " + filename, false);
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

  document.addEventListener("change", function (event) {
    var form = event.target.closest("#design-form");
    if (!form) return;
    refreshOptions(form);
    refreshStale();
  });
  document.addEventListener("input", function (event) {
    if (event.target.closest("#design-form")) refreshStale();
  });
  // A new form (tab) or a new result arrived.
  document.addEventListener("htmx:afterSettle", refreshAll);
  refreshAll();
})();
