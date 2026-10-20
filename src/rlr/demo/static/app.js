/* Related Languages Resources — demo UI */
(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const form = $("#query");
  const folio = $("#folio");
  const statusEl = $("#status");
  const map = $("#map");
  const ranking = $("#ranking");
  const readingTpl = $("#reading-tpl");
  const noteTpl = $("#note-tpl");

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const licenseBadge = (prov) => {
    const cls = prov.license_class;
    const kind = cls === "open" || cls === "noncommercial" ? "open" : cls === "derivatives_forbidden" ? "display" : "unknown";
    const label = prov.license_name || cls.replace(/_/g, " ");
    const title = kind === "open" ? "May be displayed and rendered" : kind === "display" ? "May be displayed; no derivative works" : "License unknown";
    return `<span class="badge badge--${kind}" title="${esc(title)}">${esc(label)}</span>`;
  };
  const provenance = (prov) => {
    const bits = [];
    bits.push(`<span>${esc(prov.title)}</span>`);
    if (prov.publisher) bits.push(`<span>${esc(prov.publisher)}</span>`);
    if (prov.published) bits.push(`<span>${esc(prov.published)}</span>`);
    bits.push(licenseBadge(prov));
    bits.push(`<span>${esc(prov.source)}</span>`);
    if (prov.url) bits.push(`<a href="${esc(prov.url)}" target="_blank" rel="noopener">source ↗</a>`);
    return bits.join("");
  };
  const rendering = (obj, lwcName, small = false) => {
    if (obj && obj.reason !== undefined) {
      return `<p class="rendering__absent"><b>Not available in ${esc(lwcName)}</b>${esc(obj.reason)}</p>`;
    }
    return `<div><span class="rendering__label">In ${esc(lwcName)} · ${esc(obj.provenance.source)}</span><p class="rendering__text">${esc(obj.text)}</p></div>`;
  };

  // ---------- status ----------
  fetch("/api/status").then((r) => r.json()).then((s) => {
    statusEl.innerHTML = `<b>${s.languages_with_bibles}</b> languages with Scripture in the eBible Corpus · <b>${s.glottolog_languoids.toLocaleString()}</b> Glottolog languoids · <b>${s.verses.toLocaleString()}</b> verses in the Protestant canon · notes: <b>${s.resources.length ? s.resources.join(", ") : "none configured"}</b> · MT backend: <b>${s.mt_backend}</b>`;
  }).catch(() => { statusEl.textContent = "corpus unavailable"; });

  // ---------- constellation map ----------
  function drawMap(target, lwc, related) {
    map.innerHTML = "";
    const pts = related.filter((r) => r.location).map((r) => ({ ...r, lat: r.location.lat, lon: r.location.lon, kind: r.requested ? "sel" : "rel" }));
    if (target && target.lat != null) pts.push({ code: target.code, name: target.name, lat: target.lat, lon: target.lon, kind: "target", similarity: 1 });
    if (lwc && lwc.lat != null) pts.push({ code: lwc.code, name: lwc.name, lat: lwc.lat, lon: lwc.lon, kind: "lwc", similarity: 0 });
    if (!pts.length) { map.innerHTML = `<text x="20" y="40" class="label">No coordinates to draw.</text>`; return; }
    const W = 420, H = 320, P = 36;
    let minLat = Math.min(...pts.map((p) => p.lat)), maxLat = Math.max(...pts.map((p) => p.lat));
    let minLon = Math.min(...pts.map((p) => p.lon)), maxLon = Math.max(...pts.map((p) => p.lon));
    const padDeg = Math.max(0.5, (maxLat - minLat) * 0.15, (maxLon - minLon) * 0.15);
    minLat -= padDeg; maxLat += padDeg; minLon -= padDeg; maxLon += padDeg;
    const cosLat = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
    const spanX = (maxLon - minLon) * cosLat, spanY = maxLat - minLat;
    const scale = Math.min((W - 2 * P) / spanX, (H - 2 * P) / spanY);
    const ox = (W - spanX * scale) / 2, oy = (H - spanY * scale) / 2;
    const X = (lon) => ox + (lon - minLon) * cosLat * scale;
    const Y = (lat) => oy + (maxLat - lat) * scale;
    const ns = "http://www.w3.org/2000/svg";
    const el = (tag, attrs, text) => { const e = document.createElementNS(ns, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };

    const grid = el("g", { class: "grid" });
    const step = spanY > 6 ? 2 : spanY > 2 ? 1 : 0.5;
    for (let lat = Math.ceil(minLat / step) * step; lat <= maxLat; lat += step) grid.appendChild(el("line", { x1: 0, x2: W, y1: Y(lat), y2: Y(lat) }));
    for (let lon = Math.ceil(minLon / step) * step; lon <= maxLon; lon += step) grid.appendChild(el("line", { y1: 0, y2: H, x1: X(lon), x2: X(lon) }));
    map.appendChild(grid);

    const t = pts.find((p) => p.kind === "target");
    if (t) {
      pts.filter((p) => p.kind === "rel" || p.kind === "sel").forEach((p, i) => {
        const line = el("line", { class: "link", x1: X(t.lon), y1: Y(t.lat), x2: X(p.lon), y2: Y(p.lat), style: `animation-delay:${120 + i * 80}ms` });
        map.appendChild(line);
      });
      map.appendChild(el("circle", { class: "ring", cx: X(t.lon), cy: Y(t.lat), r: 7, style: `transform-origin:${X(t.lon)}px ${Y(t.lat)}px` }));
    }
    // Labels: greedy placement so clustered languages do not overprint.
    const placed = [];
    const shortName = (n) => n.replace(/\s*\(.*?\)\s*/g, "").trim();
    const order = [...pts].sort((a, b) => (b.kind === "target") - (a.kind === "target") || (b.similarity || 0) - (a.similarity || 0));
    const boxes = (x, y, w, h) => ({ x, y, w, h });
    const collides = (b) => placed.some((o) => b.x < o.x + o.w && b.x + b.w > o.x && b.y < o.y + o.h && b.y + b.h > o.y) || b.x < 2 || b.x + b.w > W - 2 || b.y < 2 || b.y + b.h > H - 22;
    order.forEach((p, i) => {
      const r = p.kind === "target" ? 6 : p.kind === "lwc" || p.kind === "sel" ? 5 : 3 + 4 * (p.similarity || 0);
      const cx = X(p.lon), cy = Y(p.lat);
      map.appendChild(el("circle", { class: `node node--${p.kind}`, cx, cy, r, style: `animation-delay:${i * 60}ms` }));
      placed.push(boxes(cx - r, cy - r, 2 * r, 2 * r));
      const name = shortName(p.name);
      const w = name.length * 5.6 + 2, h = 11;
      const candidates = [
        { x: cx + r + 4, y: cy - h / 2, anchor: "start" },
        { x: cx - r - 4 - w, y: cy - h / 2, anchor: "end" },
        { x: cx - w / 2, y: cy - r - 4 - h, anchor: "middle" },
        { x: cx - w / 2, y: cy + r + 4, anchor: "middle" },
        { x: cx + r + 4, y: cy - r - 4 - h, anchor: "start" },
        { x: cx + r + 4, y: cy + r + 4, anchor: "start" },
        { x: cx - r - 4 - w, y: cy + r + 4, anchor: "end" },
        { x: cx - r - 4 - w, y: cy - r - 4 - h, anchor: "end" },
      ];
      const spot = candidates.find((c) => !collides(boxes(c.x, c.y, w, h))) || candidates[0];
      placed.push(boxes(spot.x, spot.y, w, h));
      const tx = spot.anchor === "start" ? spot.x : spot.anchor === "end" ? spot.x + w : spot.x + w / 2;
      map.appendChild(el("text", { class: `label label--${p.kind}`, x: tx, y: spot.y + h - 2, "text-anchor": spot.anchor }, name));
    });
    // scale bar: 100 km
    const kmPerDeg = 111.32;
    const barPx = (100 / kmPerDeg) * scale;
    const sc = el("g", { class: "scale" });
    sc.appendChild(el("line", { x1: 14, x2: 14 + barPx, y1: H - 14, y2: H - 14 }));
    sc.appendChild(el("text", { x: 14, y: H - 19 }, "100 km"));
    map.appendChild(sc);
  }

  function drawRanking(related) {
    ranking.innerHTML = related.map((r, i) => {
      const eds = r.editions || [];
      const classes = eds.map((e) => e.provenance.license_class);
      const kind = classes.some((c) => c === "open" || c === "noncommercial") ? "open" : classes.some((c) => c === "derivatives_forbidden") ? "display" : "unknown";
      const lic = kind === "open" ? "renderable" : kind === "display" ? "display only" : "no license";
      return `<li><span class="code">${String(i + 1).padStart(2, "0")}</span><span>${esc(r.name)} <span class="code">${esc(r.code)}${r.requested ? " · selected" : ""}${r.distance_km != null ? ` · ${r.distance_km} km` : ""}</span></span><span class="lic badge badge--${kind}">${lic}</span></li>`;
    }).join("");
  }

  // ---------- briefing ----------
  function renderBriefing(b) {
    const lwcName = (b.lwc_info && b.lwc_info.name) || b.context.lwc;
    const targetName = (b.target && b.target.name) || b.context.target_language;
    const [book, rest] = b.passage_label.split(" ");
    const parts = [];
    parts.push(`<header class="passage-head"><h2 class="passage-head__ref">${esc(book)} <b>${esc(rest)}</b></h2><p class="passage-head__sub">as it stands in the languages nearest <b>${esc(targetName)}</b>, read in <b>${esc(lwcName)}</b></p></header>`);
    if (b.nothing_found) {
      parts.push(`<div class="plaque"><b>Nothing to show</b>${esc(b.nothing_found.reason)}</div>`);
    }
    if (b.lwc_reading) {
      if (b.lwc_reading.reason) {
        parts.push(`<div class="plaque plaque--muted"><b>No open Bible in ${esc(lwcName)}</b>Sorry, no open Bible translation is available for ${esc(lwcName)}, so the related readings are rendered by machine where their licenses and the models allow. ${esc(b.lwc_reading.reason)}</div>`);
      } else {
        parts.push(`<article class="reading reading--lwc" style="--i:0"><header class="reading__head"><div class="reading__rank reading__rank--lwc" title="Language of wider communication">LWC</div><div><h3 class="reading__lang">${esc(lwcName)}<small>${esc(b.lwc_reading.language)}</small></h3><p class="reading__kin">the language you read · ${esc(b.lwc_reading.provenance.title || "")}</p></div></header><p class="reading__text">${esc(b.lwc_reading.text)}</p><footer class="reading__prov">${provenance(b.lwc_reading.provenance)}</footer></article>`);
      }
    }
    const wrap = document.createElement("div");
    wrap.innerHTML = parts.join("");
    b.readings.forEach((rd, i) => {
      const node = readingTpl.content.firstElementChild.cloneNode(true);
      node.style.setProperty("--i", i + 1);
      $(".reading__rank", node).textContent = String(i + 1).padStart(2, "0");
      $(".reading__lang", node).innerHTML = `${esc(rd.language.name)}<small>${esc(rd.language.code)}</small>`;
      const kin = [];
      if (rd.language.requested) kin.push("selected by you");
      if (rd.language.shared_country) kin.push("shares a country");
      if (rd.language.distance_km != null) kin.push(`${rd.language.distance_km} km away`);
      if (rd.language.path_similarity != null && rd.language.path_similarity !== rd.language.similarity) kin.push(`tree ${rd.language.path_similarity.toFixed(2)}`);
      if (rd.original.provenance.title) kin.push(rd.original.provenance.title);
      $(".reading__kin", node).textContent = kin.join(" · ");
      if (rd.language.requested) {
        $(".similarity", node).classList.add("similarity--selected");
        $(".similarity__value", node).textContent = "selected";
        $(".similarity__bar", node).remove();
      } else {
        $(".similarity__value", node).textContent = `similarity ${rd.language.similarity.toFixed(2)}`;
        const bar = $(".similarity__bar i", node);
        requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = `${Math.round(rd.language.similarity * 100)}%`; }));
      }
      $(".reading__text", node).textContent = rd.original.text;
      $(".rendering", node).innerHTML = rd.in_lwc ? rendering(rd.in_lwc, lwcName) : "";
      $(".reading__prov", node).innerHTML = provenance(rd.original.provenance);
      wrap.appendChild(node);
    });
    if (b.skipped && b.skipped.length && !b.nothing_found) {
      const p = document.createElement("p"); p.className = "skipped";
      p.innerHTML = `<b>Not shown</b> · ${b.skipped.map((s) => esc(s.reason)).join(" · ")}`;
      wrap.appendChild(p);
    }
    const notes = document.createElement("section"); notes.className = "notes";
    notes.innerHTML = `<div class="notes__head"><h2>Notes for the passage</h2><span>${b.notes.length ? `${b.notes.length} figure${b.notes.length === 1 ? "" : "s"} of speech` : "verse-indexed resources"}</span></div>`;
    if (b.no_notes) {
      notes.insertAdjacentHTML("beforeend", `<div class="plaque plaque--muted"><b>None</b>${esc(b.no_notes.reason)}</div>`);
    } else {
      const grid = document.createElement("div"); grid.className = "notes__grid";
      b.notes.forEach((n, i) => {
        const node = noteTpl.content.firstElementChild.cloneNode(true);
        node.style.setProperty("--i", i + 1);
        const fig = n.note.figure;
        const ref = `${n.note.passage.start.book} ${n.note.passage.start.chapter}:${n.note.passage.start.verse}${n.note.passage.start.verse !== n.note.passage.end.verse ? `-${n.note.passage.end.verse}` : ""}`;
        $(".note__title", node).innerHTML = `${esc(fig.label)}<small>${esc(ref)} · ${esc(fig.id)}</small>`;
        $(".note__quote", node).innerHTML = n.note.translation ? `“${esc(n.note.translation)}” ${n.note.source_text ? `<span>${esc(n.note.source_text)}</span>` : ""}` : "";
        const body = [fig.summary, n.note.comment, n.note.alternate_translations.length ? `Alternate translation: ${n.note.alternate_translations.join("; ")}` : ""].filter(Boolean).join("\n");
        $(".note__body", node).textContent = body;
        $(".note__rendering", node).innerHTML = rendering(n.in_lwc, lwcName, true);
        $(".note__prov", node).innerHTML = provenance(n.original.provenance);
        grid.appendChild(node);
      });
      notes.appendChild(grid);
    }
    wrap.appendChild(notes);
    folio.replaceChildren(...wrap.childNodes);
  }

  function showLoading(msg) {
    folio.innerHTML = `<div class="loading"><div class="loading__line"></div><div class="loading__line"></div><div class="loading__line"></div><p class="loading__caption">${esc(msg)}</p></div>`;
  }

  async function run(ev) {
    if (ev) ev.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    const btn = $(".stamp", form); btn.disabled = true;
    showLoading("Finding the neighbours, fetching the verse, checking every license…");
    $("#target-name").textContent = ""; $("#lwc-name").textContent = "";
    try {
      const qs = new URLSearchParams(data).toString();
      const [langRes, briefRes] = await Promise.all([
        fetch(`/api/languages?${new URLSearchParams({ target: data.target, lwc: data.lwc, limit: data.limit, min_similarity: data.min_similarity, include: data.include || "" })}`),
        fetch(`/api/brief?${qs}`),
      ]);
      const brief = await briefRes.json();
      if (!briefRes.ok) throw new Error(brief.detail || briefRes.statusText);
      const langs = langRes.ok ? await langRes.json() : { target: brief.target, lwc: brief.lwc_info, related: [] };
      $("#target-name").textContent = langs.target ? `${langs.target.name} · ${langs.target.countries.join(", ")}` : "unknown to Glottolog";
      $("#lwc-name").textContent = langs.lwc ? langs.lwc.name : "";
      drawMap(langs.target, langs.lwc, langs.related);
      drawRanking(langs.related);
      renderBriefing(brief);
      history.replaceState(null, "", `?${new URLSearchParams(data)}`);
    } catch (err) {
      folio.innerHTML = `<div class="plaque"><b>Could not build a briefing</b>${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false;
    }
  }

  form.addEventListener("submit", run);
  document.querySelectorAll("[data-example]").forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    const [t, l, p] = a.dataset.example.split("|");
    form.target.value = t; form.lwc.value = l; form.passage.value = p; run();
  }));
  const params = new URLSearchParams(location.search);
  if (params.get("target")) { for (const [k, v] of params) if (form[k]) form[k].value = v; }
  run();
})();
