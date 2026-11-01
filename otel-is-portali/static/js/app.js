/* =========================================================
   Otel İş Portalı — App interactions (progressive enhancement)
   Everything works without JS; this only improves the UX.
   ========================================================= */
(() => {
  "use strict";
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => [...c.querySelectorAll(s)];

  /* ---------- Dropdowns (language, account) ---------- */
  const closeAll = (except) => $$("[data-dropdown].is-open").forEach((d) => {
    if (d !== except) { d.classList.remove("is-open"); $("[data-dropdown-toggle]", d)?.setAttribute("aria-expanded", "false"); }
  });
  $$("[data-dropdown]").forEach((dd) => {
    const btn = $("[data-dropdown-toggle]", dd);
    btn?.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !dd.classList.contains("is-open");
      closeAll(dd);
      dd.classList.toggle("is-open", open);
      btn.setAttribute("aria-expanded", String(open));
    });
  });
  document.addEventListener("click", (e) => { if (!e.target.closest("[data-dropdown]")) closeAll(); });

  /* ---------- Mobile sidebar ---------- */
  const sbToggle = $("#sbToggle");
  const backdrop = $("#sbBackdrop");
  const setSidebar = (open) => {
    document.body.classList.toggle("sb-open", open);
    sbToggle?.setAttribute("aria-expanded", String(open));
    if (backdrop) backdrop.hidden = !open;
  };
  sbToggle?.addEventListener("click", () => setSidebar(!document.body.classList.contains("sb-open")));
  backdrop?.addEventListener("click", () => setSidebar(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { setSidebar(false); closeAll(); } });

  /* ---------- Toasts ---------- */
  const dismiss = (t) => { t.classList.add("is-leaving"); setTimeout(() => t.remove(), 260); };
  $$(".toast").forEach((t, i) => {
    $(".toast__close", t)?.addEventListener("click", () => dismiss(t));
    setTimeout(() => dismiss(t), 5000 + i * 600);
  });

  /* ---------- Auto-submit selects & confirm dialogs ---------- */
  $$("[data-autosubmit]").forEach((s) => s.addEventListener("change", () => s.form.submit()));
  $$("form[data-confirm]").forEach((f) => f.addEventListener("submit", (e) => {
    if (!window.confirm(f.dataset.confirm)) e.preventDefault();
  }));

  /* ---------- Number stepper ---------- */
  $$("[data-step]").forEach((b) => b.addEventListener("click", () => {
    const input = b.closest(".stepper").querySelector("input");
    const min = Number(input.min || 0), max = Number(input.max || 99);
    input.value = Math.min(max, Math.max(min, (Number(input.value) || 0) + Number(b.dataset.step)));
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }));

  /* ---------- Character counters ---------- */
  $$("[data-count-for]").forEach((out) => {
    const field = document.getElementById(out.dataset.countFor);
    field?.addEventListener("input", () => { out.textContent = field.value.length; });
  });

  /* ---------- CV upload (drag & drop + remove) ---------- */
  $$("[data-cv]").forEach((box) => {
    const input = $("input[type=file]", box);
    const drop = $("[data-drop]", box);
    const current = $("[data-cv-current]", box);
    const nameEl = $("[data-cv-name]", box);
    const err = $("[data-cv-error]", box);
    const removeFlag = $("input[name=remove_cv]", box.closest("form"));
    const max = Number(input.dataset.max || 5242880);
    const okExt = /\.(pdf|docx?)$/i;

    const showError = (msg) => { err.textContent = msg; err.hidden = !msg; box.classList.toggle("has-error", !!msg); };
    const accept = (file) => {
      if (!file) return false;
      if (!okExt.test(file.name)) { showError(err.dataset.typeMsg || "PDF, DOC, DOCX"); return false; }
      if (file.size > max) { showError(err.dataset.sizeMsg || "Max 5 MB"); return false; }
      showError("");
      nameEl.textContent = file.name;
      nameEl.removeAttribute("href");
      current.hidden = false;
      if (removeFlag) removeFlag.value = "";
      return true;
    };
    input.addEventListener("change", () => { if (!accept(input.files[0])) input.value = ""; });
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("is-over"); }));
    drop.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files[0];
      if (accept(file)) {
        const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
    $("[data-cv-remove]", box)?.addEventListener("click", () => {
      input.value = "";
      current.hidden = true;
      if (removeFlag) removeFlag.value = "on";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });

  /* ---------- Unsaved-changes indicator ---------- */
  $$("form[data-dirty-check]").forEach((form) => {
    const note = $("[data-dirty-note]", form);
    const snapshot = () => {
      const data = new FormData(form);
      return JSON.stringify([...data.entries()].filter(([k]) => k !== "csrfmiddlewaretoken").map(([k, v]) => [k, v instanceof File ? v.name : v]));
    };
    const initial = snapshot();
    let submitting = false;
    const check = () => { if (note) note.hidden = snapshot() === initial; };
    form.addEventListener("input", check);
    form.addEventListener("change", check);
    form.addEventListener("submit", () => { submitting = true; });
    window.addEventListener("beforeunload", (e) => {
      if (!submitting && snapshot() !== initial) { e.preventDefault(); e.returnValue = ""; }
    });
  });

  /* ---------- Password visibility ---------- */
  $$("[data-pw-toggle]").forEach((b) => b.addEventListener("click", () => {
    const input = b.parentElement.querySelector("input");
    input.type = input.type === "password" ? "text" : "password";
  }));

  /* ---------- Register: show employer-only fields ---------- */
  const reg = $("form[data-register]");
  if (reg) {
    const block = $("[data-employer-only]", reg);
    const sync = () => {
      const role = $("input[name=role]:checked", reg)?.value;
      block.hidden = role !== "employer";
    };
    $$("input[name=role]", reg).forEach((r) => r.addEventListener("change", sync));
    sync();
  }

  /* ---------- AI analysis: busy state while the request runs ---------- */
  $$("form[data-ai-run]").forEach((f) => f.addEventListener("submit", () => {
    const btn = $("button", f);
    btn.classList.add("is-busy");
    const label = $("span", btn);
    if (label && btn.dataset.busyLabel) label.textContent = btn.dataset.busyLabel;
  }));

  /* ---------- Profile photo: upload as soon as a file is chosen ---------- */
  $$("input[data-autosubmit-file]").forEach((input) => input.addEventListener("change", () => {
    const file = input.files[0];
    if (!file) return;
    if (input.dataset.max && file.size > Number(input.dataset.max)) {
      window.alert(input.dataset.sizeMsg || "Max 3 MB");
      input.value = "";
      return;
    }
    input.form.submit();
  }));

  // Hide broken photos (gradient placeholder shows instead)
  document.addEventListener("error", (e) => { if (e.target.tagName === "IMG") e.target.style.visibility = "hidden"; }, true);
})();
