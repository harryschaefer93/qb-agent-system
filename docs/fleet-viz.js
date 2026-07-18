/* fleet-viz.js — interactive orchestration visualization + data-driven fleet roster.
 * Self-contained (no libraries). Renders from fleet-data.json, which is generated from
 * the real pipeline spec (evals/pipelines.yaml) + agent frontmatter on every publish run.
 * Fallbacks: inline JSON -> fetch -> leave the static HTML (ASCII + hand cards) alone.
 */
(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  var COLORS = {
    QB: "#0078D4", ARCH: "#8a5cf6", QA: "#e06c75", DEV: "#2fa86b", INFRA: "#d98c2b",
    DIAGRAM: "#c057c0", DOCS: "#3a8fd0", REPO: "#5a6472", SCOUT: "#4c9a8f",
    ORACLE: "#10a37f", scoper: "#1f9e9e", retro: "#c9a227", imp: "#7d6cd9"
  };
  var TIER_LABEL = {
    judgment: "Opus-class judgment", volume: "Sonnet-class volume",
    recon: "Haiku-class recon", advisor: "Cross-family advisor"
  };
  var reducedMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- data loading ---------- */

  function loadData(cb) {
    var inline = document.getElementById("fleet-data");
    if (inline) {
      try {
        var parsed = JSON.parse(inline.textContent);
        if (parsed && parsed.pipelines) { cb(parsed); return; }
      } catch (e) { /* fall through to fetch */ }
    }
    if (window.fetch) {
      fetch("fleet-data.json").then(function (r) {
        if (!r.ok) { throw new Error("http " + r.status); }
        return r.json();
      }).then(function (d) {
        if (d && d.pipelines) { cb(d); }
      }).catch(function () { /* static fallback stays */ });
    }
  }

  /* ---------- tiny DOM helpers ---------- */

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    if (attrs) { Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); }); }
    if (text != null) { node.textContent = text; }
    return node;
  }

  function svgEl(tag, attrs) {
    var node = document.createElementNS(SVGNS, tag);
    if (attrs) { Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); }); }
    return node;
  }

  function svgText(x, y, str, attrs) {
    var t = svgEl("text", Object.assign({ x: x, y: y }, attrs || {}));
    t.textContent = str;
    return t;
  }

  /* ---------- detail card ---------- */

  var detailEl = null;

  function detailDefault() {
    if (!detailEl) { return; }
    detailEl.textContent = "";
    var p = el("p", null, "Hover or tap any node for details — agents, gates, and artifacts all come from the live pipeline spec.");
    p.style.margin = "0";
    detailEl.appendChild(p);
  }

  function showAgentDetail(data, agentId, phaseEntry) {
    var agent = null;
    for (var i = 0; i < data.agents.length; i++) {
      if (data.agents[i].id === agentId) { agent = data.agents[i]; break; }
    }
    if (!detailEl) { return; }
    detailEl.textContent = "";
    var head = el("div");
    var name = el("b", null, agentId);
    head.appendChild(name);
    if (agent) {
      head.appendChild(document.createTextNode(" — " + agent.role));
      var tier = el("span", { "class": "tier-chip" }, (TIER_LABEL[agent.tier] || agent.tier) + " · " + agent.model);
      head.appendChild(tier);
    }
    detailEl.appendChild(head);
    if (agent) {
      var blurb = el("p", null, agent.blurb);
      blurb.style.margin = "6px 0 0";
      detailEl.appendChild(blurb);
    }
    if (phaseEntry && phaseEntry.artifacts && phaseEntry.artifacts.length) {
      var lbl = el("div", null, "Produces at this phase:");
      lbl.style.marginTop = "8px";
      detailEl.appendChild(lbl);
      var ul = el("ul");
      phaseEntry.artifacts.forEach(function (a) { ul.appendChild(el("li", null, a)); });
      detailEl.appendChild(ul);
    }
    if (agent && agent.files && agent.files.length) {
      var links = el("div");
      links.style.marginTop = "8px";
      agent.files.forEach(function (f, idx) {
        if (idx > 0) { links.appendChild(document.createTextNode(" · ")); }
        var a = el("a", { href: f.href, target: "_blank", rel: "noopener" },
          f.path.replace("agents/", "") + " ↗");
        links.appendChild(a);
      });
      detailEl.appendChild(links);
    }
  }

  function showGateDetail(title, body) {
    if (!detailEl) { return; }
    detailEl.textContent = "";
    detailEl.appendChild(el("div")).appendChild(el("b", null, title));
    var p = el("p", null, body);
    p.style.margin = "6px 0 0";
    detailEl.appendChild(p);
  }

  /* ---------- layout ---------- */

  function buildLayout(pipeline, vertical) {
    var phases = pipeline.phases;
    var n = phases.length;
    var gates = [];      // {gap, kind, label, title, body}
    var cps = pipeline.checkpoints;
    ["CP1", "CP2"].forEach(function (cp) {
      gates.push({
        gap: cps[cp].before_index, kind: "cp", label: cp,
        title: cp + " — human checkpoint (hard stop)",
        body: cps[cp].purpose || cps[cp].placement
      });
    });
    if (pipeline.quality_gate_before_repo) {
      for (var qi = n - 1; qi >= 0; qi--) {
        if (phases[qi].role === "REPO") {
          gates.push({
            gap: qi, kind: "quality", label: "QG",
            title: "Quality gate (build / lint / typecheck)",
            body: "Runs before REPO. A red gate bounces the work back — up to the iteration cap of " + pipeline.iteration_cap + " cycles — instead of shipping."
          });
          break;
        }
      }
    }
    var gapGates = {};
    gates.forEach(function (g) { (gapGates[g.gap] = gapGates[g.gap] || []).push(g); });

    if (vertical) { return { vertical: true, phases: phases, gapGates: gapGates, n: n }; }

    var NW = 104, NH = 54, M = 34, BASE_GAP = 40, GATE_W = 40;
    var x = M;
    var nodes = [], gatePos = [];
    for (var i = 0; i < n; i++) {
      var gs = gapGates[i] || [];
      var gapW = (i === 0 ? 18 : BASE_GAP) + gs.length * GATE_W;
      var gateX = x + (i === 0 ? 6 : 8);
      gs.forEach(function (g, gi) {
        gatePos.push({ gate: g, x: gateX + GATE_W * gi + GATE_W / 2 });
      });
      x += gapW;
      nodes.push({ x: x, entry: phases[i] });
      x += NW;
    }
    var width = Math.max(x + M, 640);
    return {
      vertical: false, phases: phases, nodes: nodes, gates: gatePos,
      NW: NW, NH: NH, width: width,
      hub: { x: M, y: 58, w: x - M, h: 44 },
      satY: 12, nodeY: 196
    };
  }

  /* ---------- horizontal SVG ---------- */

  function renderHorizontal(data, pipeline, root) {
    var L = buildLayout(pipeline, false);
    var multi = pipeline.multi_track;
    var bounce = findBounce(pipeline.phases);
    var baseH = L.nodeY + L.NH + (bounce ? 64 : 34);
    var insetH = multi ? 140 : 0;
    var height = baseH + insetH;

    var svg = svgEl("svg", {
      "class": "viz-svg", viewBox: "0 0 " + L.width + " " + height,
      role: "img", "aria-label": "Pipeline diagram for the selected task type"
    });
    svg.style.minWidth = "640px";

    var defs = svgEl("defs");
    var marker = svgEl("marker", {
      id: "arrow", viewBox: "0 0 8 8", refX: "7", refY: "4",
      markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse"
    });
    var mpath = svgEl("path", { d: "M0,0 L8,4 L0,8 z", fill: "#50B0F6" });
    marker.appendChild(mpath);
    defs.appendChild(marker);
    svg.appendChild(defs);

    /* satellites */
    renderSatellite(svg, data, "SCOUT", L.hub.x + 8, L.satY, "recon before CP2");
    renderSatellite(svg, data, "ORACLE", L.hub.x + L.hub.w - 158, L.satY, "advisory · on conflict");

    /* QB hub */
    var hub = svgEl("g", { "class": "node", tabindex: "0", role: "button", "aria-label": "QB orchestrator" });
    hub.appendChild(svgEl("rect", {
      x: L.hub.x, y: L.hub.y, width: L.hub.w, height: L.hub.h, rx: 10,
      fill: "rgba(0,120,212,.22)", stroke: COLORS.QB, "stroke-width": 1.4
    }));
    hub.appendChild(svgText(L.hub.x + L.hub.w / 2, L.hub.y + 20, "QB — orchestrator", {
      fill: "#e8eef9", "font-size": 14, "font-weight": 700, "text-anchor": "middle"
    }));
    hub.appendChild(svgText(L.hub.x + L.hub.w / 2, L.hub.y + 36,
      "dispatches every phase · driver enforces the order (pipelines.yaml + run-state)", {
        fill: "#aab6cf", "font-size": 10.5, "text-anchor": "middle"
      }));
    attachDetail(hub, function () { showAgentDetail(data, "QB", null); });
    svg.appendChild(hub);

    /* baseline connector through the phase row */
    var midY = L.nodeY + L.NH / 2;
    svg.appendChild(svgEl("path", {
      d: "M " + (L.hub.x + 4) + " " + midY + " H " + (L.hub.x + L.hub.w - 4),
      stroke: "#25324f", "stroke-width": 2, fill: "none"
    }));

    /* dispatch paths + phase nodes */
    var dispatchPaths = [];
    L.nodes.forEach(function (nd, i) {
      var cx = nd.x + L.NW / 2;
      var p = svgEl("path", {
        d: "M " + cx + " " + (L.hub.y + L.hub.h) + " L " + cx + " " + L.nodeY,
        stroke: "rgba(80,176,246,.4)", "stroke-width": 1.3, fill: "none",
        "stroke-dasharray": "3 4", "marker-end": "url(#arrow)"
      });
      svg.appendChild(p);
      dispatchPaths.push(p);

      var entry = nd.entry;
      var g = svgEl("g", {
        "class": "node", tabindex: "0", role: "button",
        "aria-label": "Phase " + (i + 1) + ": " + entry.role
      });
      g.appendChild(svgEl("rect", {
        x: nd.x, y: L.nodeY, width: L.NW, height: L.NH, rx: 9,
        fill: COLORS[entry.role] || "#3a8fd0", "fill-opacity": ".9",
        stroke: "rgba(255,255,255,.18)"
      }));
      g.appendChild(svgText(nd.x + L.NW / 2, L.nodeY + 24, entry.role, {
        fill: "#fff", "font-size": 14.5, "font-weight": 800, "text-anchor": "middle",
        "letter-spacing": ".4"
      }));
      g.appendChild(svgText(nd.x + L.NW / 2, L.nodeY + 41, "phase " + (i + 1), {
        fill: "rgba(255,255,255,.75)", "font-size": 10, "text-anchor": "middle"
      }));
      attachDetail(g, function () { showAgentDetail(data, entry.role, entry); });
      svg.appendChild(g);
      nd.el = g;
    });

    /* gates */
    var gateEls = {};
    L.gates.forEach(function (gp) {
      var g = svgEl("g", { "class": "gate", tabindex: "0", role: "button", "aria-label": gp.gate.title });
      var y = midY;
      var shape;
      if (gp.gate.kind === "cp") {
        shape = svgEl("path", {
          "class": "gate-shape",
          d: "M " + gp.x + " " + (y - 15) + " L " + (gp.x + 13) + " " + y +
             " L " + gp.x + " " + (y + 15) + " L " + (gp.x - 13) + " " + y + " Z",
          fill: "rgba(242,201,76,.16)", stroke: "#f2c94c", "stroke-width": 1.5
        });
      } else {
        shape = svgEl("rect", {
          "class": "gate-shape", x: gp.x - 12, y: y - 12, width: 24, height: 24, rx: 5,
          transform: "rotate(45 " + gp.x + " " + y + ")",
          fill: "rgba(47,168,107,.16)", stroke: "#2fa86b", "stroke-width": 1.5
        });
      }
      g.appendChild(shape);
      g.appendChild(svgText(gp.x, y - 22, gp.gate.label, {
        fill: gp.gate.kind === "cp" ? "#f2c94c" : "#2fa86b",
        "font-size": 10.5, "font-weight": 700, "text-anchor": "middle"
      }));
      attachDetail(g, function () { showGateDetail(gp.gate.title, gp.gate.body); });
      svg.appendChild(g);
      (gateEls[gp.gate.gap] = gateEls[gp.gate.gap] || []).push(g);
    });

    /* iteration-cap bounce arrow */
    if (bounce) {
      var from = L.nodes[bounce.qa], to = L.nodes[bounce.dev];
      var fx = from.x + L.NW / 2, tx = to.x + L.NW / 2;
      var by = L.nodeY + L.NH;
      svg.appendChild(svgEl("path", {
        d: "M " + fx + " " + by + " C " + fx + " " + (by + 40) + ", " + tx + " " + (by + 40) + ", " + tx + " " + (by + 4),
        stroke: "#e06c75", "stroke-width": 1.3, fill: "none",
        "stroke-dasharray": "5 4", "marker-end": "url(#arrow)", opacity: ".8"
      }));
      svg.appendChild(svgText((fx + tx) / 2, by + 52,
        "bounce on fail · ≤" + pipeline.iteration_cap + " cycles, then escalate", {
          fill: "#e06c75", "font-size": 10.5, "text-anchor": "middle"
        }));
    }

    /* fan-out inset */
    if (multi) { renderFanout(svg, data, pipeline, L, baseH); }

    root.appendChild(svg);
    return { svg: svg, layout: L, dispatchPaths: dispatchPaths, gateEls: gateEls };
  }

  function findBounce(phases) {
    var dev = -1;
    for (var i = 0; i < phases.length; i++) {
      if (phases[i].role === "DEV" || phases[i].role === "INFRA") { dev = i; }
      else if (phases[i].role === "QA" && dev >= 0) { return { qa: i, dev: dev }; }
    }
    return null;
  }

  function renderSatellite(svg, data, id, x, y, note) {
    var w = 150, h = 30;
    var g = svgEl("g", { "class": "node", tabindex: "0", role: "button", "aria-label": id + " — " + note });
    g.appendChild(svgEl("rect", {
      x: x, y: y, width: w, height: h, rx: 15,
      fill: "rgba(255,255,255,.03)", stroke: COLORS[id], "stroke-width": 1.2, "stroke-dasharray": "4 3"
    }));
    g.appendChild(svgText(x + 12, y + 19, id, { fill: COLORS[id], "font-size": 11.5, "font-weight": 800 }));
    g.appendChild(svgText(x + (id === "SCOUT" ? 58 : 66), y + 19, note, { fill: "#aab6cf", "font-size": 10 }));
    attachDetail(g, function () {
      var sat = data.satellites[id] || {};
      showGateDetail(id + " — " + (sat.role || ""), (sat.when || "") + (sat.note ? " " + sat.note : "") + (sat.returns ? " Returns: " + sat.returns : ""));
    });
    svg.appendChild(g);
  }

  function renderFanout(svg, data, pipeline, L, topY) {
    var devNode = null;
    for (var i = 0; i < L.nodes.length; i++) {
      if (L.nodes[i].entry.role === "DEV") { devNode = L.nodes[i]; break; }
    }
    if (!devNode) { return; }
    var fx = devNode.x + L.NW / 2;
    var y = topY + 6;
    var ex = data.fanout_example;

    svg.appendChild(svgEl("path", {
      d: "M " + fx + " " + (L.nodeY + L.NH) + " L " + fx + " " + (y + 12),
      stroke: "rgba(47,168,107,.6)", "stroke-width": 1.2, fill: "none", "stroke-dasharray": "2 3"
    }));
    svg.appendChild(svgText(L.hub.x + 4, y + 10,
      "multi-track fan-out — each track in its own git worktree (illustrative example):", {
        fill: "#aab6cf", "font-size": 11
      }));

    var chipW = 118, chipH = 30, gap = 16;
    var totalW = ex.tracks.length * chipW + (ex.tracks.length - 1) * gap + 130;
    var startX = Math.max(L.hub.x + 4, Math.min(fx - totalW / 2, L.width - totalW - 20));
    var cy = y + 26;
    var chipPos = {};
    ex.tracks.forEach(function (t, ti) {
      var cxp = startX + ti * (chipW + gap);
      chipPos[t.name] = { x: cxp, y: cy };
      var g = svgEl("g", { "class": "node", tabindex: "0", role: "button", "aria-label": "track " + t.name });
      g.appendChild(svgEl("rect", {
        x: cxp, y: cy, width: chipW, height: chipH, rx: 7,
        fill: "rgba(47,168,107,.12)", stroke: "#2fa86b", "stroke-width": 1.1
      }));
      g.appendChild(svgText(cxp + chipW / 2, cy + 13, "track/" + t.name, {
        fill: "#d6e2f5", "font-size": 10.5, "font-weight": 700, "text-anchor": "middle"
      }));
      g.appendChild(svgText(cxp + chipW / 2, cy + 25, t.framework, {
        fill: "#aab6cf", "font-size": 9, "text-anchor": "middle"
      }));
      attachDetail(g, function () {
        showGateDetail("Track " + t.name + " (" + t.framework + ")",
          "Owns " + t.owned_paths.join(", ") +
          (t.depends_on.length ? " · depends on: " + t.depends_on.join(", ") : " · no dependencies — runs in the first wave") +
          ". Isolated worktree; merges are attributed per track. " + ex.note);
      });
      svg.appendChild(g);
    });
    ex.tracks.forEach(function (t) {
      t.depends_on.forEach(function (dep) {
        var a = chipPos[dep], b = chipPos[t.name];
        if (!a || !b) { return; }
        svg.appendChild(svgEl("path", {
          d: "M " + (a.x + chipW) + " " + (a.y + chipH / 2) + " L " + (b.x - 3) + " " + (b.y + chipH / 2),
          stroke: "#d98c2b", "stroke-width": 1.2, fill: "none", "marker-end": "url(#arrow)"
        }));
      });
    });
    var mx = startX + ex.tracks.length * (chipW + gap) + 6;
    var mg = svgEl("g", { "class": "gate", tabindex: "0", role: "button", "aria-label": "attributed merge" });
    mg.appendChild(svgEl("rect", {
      "class": "gate-shape", x: mx, y: cy, width: 108, height: chipH, rx: 7,
      fill: "rgba(90,100,114,.25)", stroke: "#8a94a6", "stroke-width": 1.1
    }));
    mg.appendChild(svgText(mx + 54, cy + 19, "attributed merge", {
      fill: "#d6e2f5", "font-size": 10, "text-anchor": "middle"
    }));
    attachDetail(mg, function () { showGateDetail("Attributed merge", ex.merge); });
    svg.appendChild(mg);
  }

  /* ---------- vertical (narrow) rendering ---------- */

  function renderVertical(data, pipeline, root) {
    var phases = pipeline.phases;
    var W = 360, M = 14, railX = 34, nodeX = 62, nodeW = W - nodeX - M, NH = 46, VG = 38;
    var gapGates = buildLayout(pipeline, true).gapGates;
    var y = 14;
    var svg = svgEl("svg", { "class": "viz-svg", role: "img", "aria-label": "Pipeline diagram (vertical)" });

    var hub = svgEl("g", { "class": "node", tabindex: "0", role: "button", "aria-label": "QB orchestrator" });
    hub.appendChild(svgEl("rect", {
      x: M, y: y, width: W - 2 * M, height: 40, rx: 9,
      fill: "rgba(0,120,212,.22)", stroke: COLORS.QB, "stroke-width": 1.3
    }));
    hub.appendChild(svgText(W / 2, y + 18, "QB — orchestrator", {
      fill: "#e8eef9", "font-size": 13, "font-weight": 700, "text-anchor": "middle"
    }));
    hub.appendChild(svgText(W / 2, y + 32, "SCOUT recon · ORACLE advisory · driver-enforced", {
      fill: "#aab6cf", "font-size": 9.5, "text-anchor": "middle"
    }));
    attachDetail(hub, function () { showAgentDetail(data, "QB", null); });
    svg.appendChild(hub);
    y += 56;
    var railTop = y;

    phases.forEach(function (entry, i) {
      (gapGates[i] || []).forEach(function (g) {
        var gg = svgEl("g", { "class": "gate", tabindex: "0", role: "button", "aria-label": g.title });
        gg.appendChild(svgEl("path", {
          "class": "gate-shape",
          d: "M " + railX + " " + (y + 2) + " l 10 9 l -10 9 l -10 -9 z",
          fill: g.kind === "cp" ? "rgba(242,201,76,.16)" : "rgba(47,168,107,.16)",
          stroke: g.kind === "cp" ? "#f2c94c" : "#2fa86b", "stroke-width": 1.3
        }));
        var gateNote = g.kind === "cp" ? "human checkpoint (hard stop)" : "quality gate (bounce on fail)";
        gg.appendChild(svgText(railX + 18, y + 15, g.label + " — " + gateNote, {
          fill: g.kind === "cp" ? "#f2c94c" : "#2fa86b", "font-size": 9.5
        }));
        attachDetail(gg, function () { showGateDetail(g.title, g.body); });
        svg.appendChild(gg);
        y += 28;
      });
      var g = svgEl("g", { "class": "node", tabindex: "0", role: "button", "aria-label": "Phase " + (i + 1) + ": " + entry.role });
      g.appendChild(svgEl("path", {
        d: "M " + railX + " " + (y + NH / 2) + " H " + (nodeX - 4),
        stroke: "rgba(80,176,246,.4)", "stroke-width": 1.2, fill: "none"
      }));
      g.appendChild(svgEl("rect", {
        x: nodeX, y: y, width: nodeW, height: NH, rx: 8,
        fill: COLORS[entry.role] || "#3a8fd0", "fill-opacity": ".9", stroke: "rgba(255,255,255,.18)"
      }));
      g.appendChild(svgText(nodeX + 14, y + 20, entry.role, {
        fill: "#fff", "font-size": 13.5, "font-weight": 800
      }));
      g.appendChild(svgText(nodeX + 14, y + 36, "phase " + (i + 1) +
        (entry.artifacts.length ? " · " + entry.artifacts.length + " artifact" + (entry.artifacts.length > 1 ? "s" : "") : ""), {
          fill: "rgba(255,255,255,.75)", "font-size": 9.5
        }));
      attachDetail(g, function () { showAgentDetail(data, entry.role, entry); });
      svg.appendChild(g);
      entry._vy = y;
      y += NH + (VG - 24);
    });

    svg.insertBefore(svgEl("path", {
      d: "M " + railX + " " + railTop + " L " + railX + " " + (y - 10),
      stroke: "#25324f", "stroke-width": 2, fill: "none"
    }), svg.childNodes[1]);

    if (pipeline.multi_track) {
      svg.appendChild(svgText(M + 4, y + 6,
        "DEV fans out to parallel worktree tracks (see desktop view for the inset)", {
          fill: "#aab6cf", "font-size": 10
        }));
      y += 20;
    }
    svg.setAttribute("viewBox", "0 0 " + W + " " + (y + 8));
    root.appendChild(svg);
    return { svg: svg };
  }

  /* ---------- interactivity plumbing ---------- */

  function attachDetail(node, fn) {
    node.addEventListener("mouseenter", fn);
    node.addEventListener("focus", fn);
    node.addEventListener("click", fn);
  }

  /* ---------- animation (horizontal only) ---------- */

  var animToken = { cancelled: true };

  function animate(ctx, pipeline) {
    animToken.cancelled = true;
    if (reducedMotion || !ctx || ctx.layout === undefined) { return; }
    var token = { cancelled: false };
    animToken = token;
    var L = ctx.layout;
    var pulse = svgEl("circle", { "class": "pulse", r: 5, fill: "#50B0F6", opacity: "0" });
    ctx.svg.appendChild(pulse);

    function move(pathEl, dur, reverse) {
      return new Promise(function (resolve) {
        var len = pathEl.getTotalLength();
        var start = null;
        function frame(ts) {
          if (token.cancelled) { resolve(); return; }
          if (start === null) { start = ts; }
          var t = Math.min((ts - start) / dur, 1);
          var at = reverse ? (1 - t) * len : t * len;
          var pt = pathEl.getPointAtLength(at);
          pulse.setAttribute("cx", pt.x); pulse.setAttribute("cy", pt.y);
          pulse.setAttribute("opacity", "1");
          if (t < 1) { requestAnimationFrame(frame); } else { resolve(); }
        }
        requestAnimationFrame(frame);
      });
    }
    function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

    (async function run() {
      while (!token.cancelled) {
        for (var i = 0; i < L.nodes.length && !token.cancelled; i++) {
          var gateGroup = ctx.gateEls[i];
          if (gateGroup) {
            for (var gi = 0; gi < gateGroup.length && !token.cancelled; gi++) {
              gateGroup[gi].classList.add("flash");
              await wait(420);
              gateGroup[gi].classList.remove("flash");
            }
          }
          if (token.cancelled) { break; }
          await move(ctx.dispatchPaths[i], 340, false);
          L.nodes[i].el.classList.add("active");
          await wait(430);
          await move(ctx.dispatchPaths[i], 300, true);
          L.nodes[i].el.classList.remove("active");
          pulse.setAttribute("opacity", "0");
        }
        if (!token.cancelled) { await wait(1700); }
      }
      pulse.remove();
    })();
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { animToken.cancelled = true; }
  });

  /* ---------- chips + top-level render ---------- */

  function renderViz(data, root, taskType) {
    var old = root.querySelector(".viz-stage");
    if (old) { old.remove(); }
    animToken.cancelled = true;
    var stage = el("div", { "class": "viz-stage" });
    root.appendChild(stage);
    var pipeline = data.pipelines[taskType];
    var vertical = root.clientWidth > 0 && root.clientWidth < 620;
    var ctx = vertical ? renderVertical(data, pipeline, stage)
                       : renderHorizontal(data, pipeline, stage);
    if (!vertical) { animate(ctx, pipeline); }
    var cap = el("div", { "class": "viz-legend" });
    cap.appendChild(el("span", null, "◆ human checkpoint (hard stop)"));
    cap.appendChild(el("span", null, "▣ quality gate (bounce on fail)"));
    cap.appendChild(el("span", null, "⇢ QB dispatch (one phase at a time)"));
    cap.appendChild(el("span", null, "fingerprint " + data.meta.source_fingerprint));
    stage.appendChild(cap);
  }

  function boot(data) {
    var root = document.getElementById("viz-root");
    if (!root || !data.task_types || !data.task_types.length) { return; }

    var chips = el("div", { "class": "task-chips", role: "tablist", "aria-label": "Task type" });
    var current = data.task_types.indexOf("full-delivery") >= 0 ? "full-delivery" : data.task_types[0];
    data.task_types.forEach(function (t) {
      var c = el("button", { "class": "chip", role: "tab", "aria-selected": String(t === current) }, t);
      c.addEventListener("click", function () {
        current = t;
        chips.querySelectorAll(".chip").forEach(function (x) { x.setAttribute("aria-selected", "false"); });
        c.setAttribute("aria-selected", "true");
        renderViz(data, root, current);
        detailDefault();
      });
      chips.appendChild(c);
    });
    root.appendChild(chips);

    detailEl = el("div", { "class": "viz-detail", "aria-live": "polite" });
    renderViz(data, root, current);
    root.appendChild(detailEl);
    detailDefault();

    var resizeTimer = null;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () { renderViz(data, root, current); }, 220);
    });

    renderFleet(data);
  }

  /* ---------- data-driven fleet cards ---------- */

  function renderFleet(data) {
    var wrap = document.getElementById("fleet-cards");
    if (!wrap || !data.agents || data.agents.length === 0) { return; }
    var frag = document.createDocumentFragment();
    data.agents.forEach(function (a) {
      var card = el("div", { "class": "agent" + (a.id === "QB" ? " qb" : "") });
      var top = el("div", { "class": "top" });
      top.appendChild(el("span", { "class": "tag t-" + a.id.toLowerCase() }, a.id));
      top.appendChild(el("span", { "class": "role" },
        a.role + " · " + (TIER_LABEL[a.tier] || a.tier).replace("-class", "")));
      card.appendChild(top);
      card.appendChild(el("p", null, a.blurb));
      var links = el("div", { "class": "links" });
      a.files.forEach(function (f) {
        links.appendChild(el("a", { href: f.href, target: "_blank", rel: "noopener" },
          f.path.replace("agents/", "") + " ↗"));
      });
      card.appendChild(links);
      frag.appendChild(card);
    });
    wrap.textContent = "";
    wrap.appendChild(frag);
  }

  /* ---------- go ---------- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { loadData(boot); });
  } else {
    loadData(boot);
  }
})();
