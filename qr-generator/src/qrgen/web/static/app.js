// Front end for the qrgen web app. The server builds the payload and draws the code.
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };

  var EC_HINT = {
    L: "Recovers about 7% damage. Largest capacity.",
    M: "Recovers about 15% damage. A good default.",
    Q: "Recovers about 25% damage.",
    H: "Recovers about 30% damage. Best for printed or worn codes."
  };
  var EMPTY_MSG = "Fill in the details to see your code here.";

  // Field ids match what qrgen.payloads.build() reads on the server.
  var MODES = {
    link: { label: "Link", fields: [
      { id: "url", label: "Web address", type: "url", ph: "https://example.com", value: "https://example.com" }
    ] },
    text: { label: "Text", fields: [
      { id: "text", label: "Text", type: "textarea", ph: "Any message, note or code" }
    ] },
    wifi: { label: "Wi-Fi", fields: [
      { id: "ssid", label: "Network name", type: "text", ph: "Network name (SSID)" },
      { id: "password", label: "Password", type: "text", ph: "Leave blank for an open network" },
      { id: "security", label: "Security", type: "select", options: [["WPA", "WPA / WPA2 / WPA3"], ["WEP", "WEP"], ["nopass", "None"]], value: "WPA" },
      { id: "hidden", label: "Hidden network", type: "checkbox" }
    ] },
    contact: { label: "Contact", fields: [
      { id: "first", label: "First name", type: "text", pair: true },
      { id: "last", label: "Last name", type: "text", pair: true },
      { id: "org", label: "Organization", type: "text", pair: true },
      { id: "title", label: "Job title", type: "text", pair: true },
      { id: "phone", label: "Phone", type: "tel", ph: "+1 555 123 4567", pair: true },
      { id: "email", label: "Email", type: "email", ph: "name@example.com", pair: true },
      { id: "website", label: "Website", type: "url", ph: "https://example.com" }
    ] },
    whatsapp: { label: "WhatsApp", fields: [
      { id: "phone", label: "Phone number", type: "tel", ph: "15551234567", hint: "Country code first, digits only, no plus sign." },
      { id: "message", label: "Pre-filled message (optional)", type: "textarea", ph: "Hello! I scanned your code." }
    ] },
    email: { label: "Email", fields: [
      { id: "to", label: "To", type: "email", ph: "name@example.com" },
      { id: "subject", label: "Subject (optional)", type: "text" },
      { id: "body", label: "Message (optional)", type: "textarea" }
    ] }
  };

  var PRESETS = [
    { name: "Ink", fg: "#111111", bg: "#ffffff" },
    { name: "Navy", fg: "#14213d", bg: "#ffffff" },
    { name: "Forest", fg: "#0b5d3b", bg: "#ffffff" },
    { name: "Plum", fg: "#4a1d5c", bg: "#ffffff" }
  ];

  var state = { kind: "link", ec: "M", shape: "square", size: 1024, border: 4, fg: "#111111", bg: "#ffffff" };
  var values = {};
  Object.keys(MODES).forEach(function (k) {
    values[k] = {};
    MODES[k].fields.forEach(function (f) { if (f.value !== undefined) values[k][f.id] = f.value; });
  });

  var current = null;   // last successful response
  var timer = null;
  var controller = null;
  var seq = 0;

  /* ---------- tabs and fields ---------- */
  function renderTabs() {
    var host = $("#tabs");
    host.innerHTML = "";
    Object.keys(MODES).forEach(function (k) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab";
      b.id = "tab-" + k;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(k === state.kind));
      b.textContent = MODES[k].label;
      b.addEventListener("click", function () {
        state.kind = k;
        renderTabs();
        renderFields();
        schedule(0);
      });
      host.appendChild(b);
    });
    $("#fields").setAttribute("aria-labelledby", "tab-" + state.kind);
  }

  function renderFields() {
    var host = $("#fields");
    host.innerHTML = "";
    var kind = state.kind, pending = [];
    function flush() {
      if (!pending.length) return;
      var row = document.createElement("div");
      row.className = "row2";
      pending.forEach(function (n) { row.appendChild(n); });
      host.appendChild(row);
      pending = [];
    }
    MODES[kind].fields.forEach(function (f) {
      var wrap = document.createElement("div");
      wrap.className = "field";
      var id = "f-" + kind + "-" + f.id, input;
      if (f.type === "checkbox") {
        wrap.innerHTML = '<label class="check"><input type="checkbox" id="' + id + '"><span></span></label>';
        wrap.querySelector("span").textContent = f.label;
        input = wrap.querySelector("input");
        input.checked = !!values[kind][f.id];
        input.addEventListener("change", function () { values[kind][f.id] = input.checked; schedule(0); });
      } else {
        var lab = document.createElement("label");
        lab.setAttribute("for", id);
        lab.textContent = f.label;
        wrap.appendChild(lab);
        if (f.type === "textarea") input = document.createElement("textarea");
        else if (f.type === "select") {
          input = document.createElement("select");
          f.options.forEach(function (o) {
            var op = document.createElement("option");
            op.value = o[0];
            op.textContent = o[1];
            input.appendChild(op);
          });
        } else {
          input = document.createElement("input");
          input.type = f.type;
          input.autocomplete = "off";
        }
        input.id = id;
        if (f.ph) input.placeholder = f.ph;
        input.value = values[kind][f.id] !== undefined ? values[kind][f.id] : "";
        var onChange = function () { values[kind][f.id] = input.value; schedule(200); };
        input.addEventListener("input", onChange);
        input.addEventListener("change", onChange);
        wrap.appendChild(input);
        if (f.hint) {
          var h = document.createElement("p");
          h.className = "hint";
          h.textContent = f.hint;
          wrap.appendChild(h);
        }
      }
      if (f.pair) { pending.push(wrap); if (pending.length === 2) flush(); }
      else { flush(); host.appendChild(wrap); }
    });
    flush();
  }

  /* ---------- server calls ---------- */
  function body(extra) {
    var b = {
      kind: state.kind,
      fields: values[state.kind],
      style: { fg: state.fg, bg: state.bg, shape: state.shape, border: state.border, ec: state.ec },
      size: state.size
    };
    if (extra) Object.keys(extra).forEach(function (k) { b[k] = extra[k]; });
    return JSON.stringify(b);
  }

  function isBlank() {
    var v = values[state.kind];
    return !Object.keys(v).some(function (k) {
      var f = MODES[state.kind].fields.filter(function (x) { return x.id === k; })[0];
      return f && f.type !== "checkbox" && f.type !== "select" && String(v[k]).trim() !== "";
    });
  }

  function schedule(delay) {
    clearTimeout(timer);
    timer = setTimeout(generate, delay);
  }

  function setStatus(t) { $("#status").textContent = t || ""; }

  function showEmpty(msg) {
    current = null;
    $("#qr-img").hidden = true;
    $("#empty").hidden = false;
    $("#empty").textContent = msg;
    $("#meta").hidden = true;
    $("#payload").value = "";
    ["#save-png", "#save-svg", "#copy"].forEach(function (s) { $(s).disabled = true; });
  }

  function render(d) {
    current = d;
    var img = $("#qr-img");
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(d.svg);
    img.hidden = false;
    $("#empty").hidden = true;
    $("#m-ver").textContent = d.version + " of 40";
    $("#m-grid").textContent = d.modules + " × " + d.modules + " modules";
    $("#m-bytes").textContent = d.bytes + (d.bytes === 1 ? " byte" : " bytes");
    $("#m-png").textContent = d.png_px + " × " + d.png_px + " px";
    $("#meta").hidden = false;
    $("#payload").value = d.payload;
    ["#save-png", "#save-svg", "#copy"].forEach(function (s) { $(s).disabled = false; });
  }

  function updateLabels() {
    $("#ec-hint").textContent = EC_HINT[state.ec];
    $("#quiet-out").textContent = state.border + (state.border === 1 ? " module" : " modules");
    $("#fg-hex").textContent = state.fg;
    $("#bg-hex").textContent = state.bg;
  }

  function generate() {
    updateLabels();
    setStatus("");
    if (isBlank()) { showEmpty(EMPTY_MSG); setNote(""); return; }
    if (controller) controller.abort();
    controller = new AbortController();
    var mine = ++seq;
    fetch("api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body(),
      signal: controller.signal
    }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (r) {
      if (mine !== seq) return;
      if (!r.ok) { showEmpty(r.data.error || "Something went wrong."); return; }
      render(r.data);
      setNote(r.data.warning);
    }).catch(function (e) {
      if (e && e.name === "AbortError") return;
      showEmpty("Could not reach the server. Check that it is running.");
    });
  }

  function setNote(msg) {
    var n = $("#contrast-note");
    n.textContent = msg || "";
    n.classList.toggle("on", !!msg);
  }

  function download(fmt) {
    if (!current) return;
    setStatus("Preparing " + fmt.toUpperCase() + "…");
    fetch("api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body({ format: fmt })
    }).then(function (res) {
      if (!res.ok) return res.json().then(function (d) { throw new Error(d.error || "Download failed."); });
      return res.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      var name = "qr-" + state.kind + "." + fmt;
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      setStatus("Saved " + name + ".");
    }).catch(function (e) { setStatus(e.message || "Download failed."); });
  }

  $("#save-png").addEventListener("click", function () { download("png"); });
  $("#save-svg").addEventListener("click", function () { download("svg"); });

  $("#copy").addEventListener("click", function () {
    if (!current) return;
    var ta = $("#payload");
    function fallback() {
      ta.focus(); ta.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      setStatus(ok ? "Copied the encoded text." : "Selected the text. Press Ctrl+C or Cmd+C to copy.");
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(current.payload).then(function () { setStatus("Copied the encoded text."); }, fallback);
    } else fallback();
  });

  /* ---------- options ---------- */
  function radios(name, key, num) {
    Array.prototype.forEach.call(document.querySelectorAll('input[name="' + name + '"]'), function (r) {
      r.checked = String(state[key]) === r.value;
      r.addEventListener("change", function () {
        if (!r.checked) return;
        state[key] = num ? Number(r.value) : r.value;
        schedule(0);
      });
    });
  }
  radios("ec", "ec", false);
  radios("shape", "shape", false);
  radios("size", "size", true);

  $("#fg").addEventListener("input", function (e) { state.fg = e.target.value; updateLabels(); schedule(80); });
  $("#bg").addEventListener("input", function (e) { state.bg = e.target.value; updateLabels(); schedule(80); });
  $("#quiet").addEventListener("input", function (e) { state.border = Number(e.target.value); updateLabels(); schedule(80); });

  PRESETS.forEach(function (p) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "preset";
    var sw = document.createElement("i");
    sw.style.background = p.fg;
    b.appendChild(sw);
    b.appendChild(document.createTextNode(p.name));
    b.addEventListener("click", function () {
      state.fg = p.fg; state.bg = p.bg;
      $("#fg").value = p.fg; $("#bg").value = p.bg;
      updateLabels();
      schedule(0);
    });
    $("#presets").appendChild(b);
  });

  /* ---------- boot ---------- */
  renderTabs();
  renderFields();
  updateLabels();
  generate();
})();
