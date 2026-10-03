// Log viewer for logs.html. nginx serves a JSON listing of /config/GivTCP/logs at logs/ and the .log files
// themselves (see ingress.conf). Files are read from the end with HTTP Range requests, so large logs load
// quickly, and follow mode only fetches the bytes added since the last read.
// A tick box per log type: tick one to see it alone, or several (any combination) to merge them by timestamp.
(function() {
    var CHUNK = 256 * 1024;         // bytes read from the end of a file (and per "Load earlier")
    var MAX_LINES = 20000;          // keep the page responsive on very large logs
    var FOLLOW_MS = 5000;
    var LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
    var TIMESTAMP = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})/;     // every GivTCP log line starts with one

    var el = function(id) { return document.getElementById(id); };
    // selected: the ticked logs (their base names). day: null for the current files, or a rotated day.
    // sources: the files being shown
    var state = { groups: [], selected: null, day: null, sources: [], timer: null };

    // ---- Log types: one tick box each, rotated days of the same log grouped under it ----
    function describe(base) {
        var m;
        if (base === "startup.log") return { label: "Startup", tag: "Startup", order: "0" };
        if ((m = base.match(/^log_inv_(\d+)\.log$/))) return { label: "Inverter " + m[1], tag: "Inv " + m[1], order: "1-" + pad(m[1]) + "-0" };
        if ((m = base.match(/^write_log_inv_(\d+)\.log$/))) return { label: "Inverter " + m[1] + " writes", tag: "Inv " + m[1] + " write", order: "1-" + pad(m[1]) + "-1" };
        if ((m = base.match(/^rest_log_inv_(\d+)\.log$/))) return { label: "Inverter " + m[1] + " REST", tag: "Inv " + m[1] + " REST", order: "1-" + pad(m[1]) + "-2" };
        if ((m = base.match(/^rest_gunicorn_inv_(\d+)\.log$/))) return { label: "Inverter " + m[1] + " REST server", tag: "Inv " + m[1] + " gunicorn", order: "1-" + pad(m[1]) + "-3" };
        if (base === "rest_gunicorn_settings.log") return { label: "Settings server", tag: "Settings srv", order: "0-1" };
        if (base === "log_evc.log") return { label: "EV charger", tag: "EVC", order: "2-0" };
        if (base === "write_log_evc.log") return { label: "EV charger writes", tag: "EVC write", order: "2-1" };
        return { label: base, tag: base.replace(/\.log$/, ""), order: "3-" + base };
    }
    function pad(n) { return ("000" + n).slice(-3); }

    function groupFiles(listing) {
        var groups = {};
        listing.forEach(function(f) {
            if (f.type !== "file") return;
            // Rotated days are name.YYYY-MM-DD.log (#606), or name.log.YYYY-MM-DD from older versions
            var m = f.name.match(/^(.+)\.(\d{4}-\d{2}-\d{2})\.log$/);
            if (m) m = [m[0], m[1] + ".log", m[2]];
            else m = f.name.match(/^(.+\.log)(?:\.(\d{4}-\d{2}-\d{2}))?$/);
            if (!m) return;
            var g = groups[m[1]] || (groups[m[1]] = { base: m[1], files: [] });
            g.files.push({ name: f.name, day: m[2] || null, size: f.size, mtime: f.mtime });
        });
        return Object.keys(groups).map(function(k) {
            var g = groups[k], d = describe(k);
            g.label = d.label; g.tag = d.tag; g.order = d.order;
            // current file first, then rotated days newest first
            g.files.sort(function(a, b) { return a.day === b.day ? 0 : !a.day ? -1 : !b.day ? 1 : (a.day < b.day ? 1 : -1); });
            return g;
        }).sort(function(a, b) { return a.order < b.order ? -1 : 1; })
          .map(function(g, i) { g.colour = i % 8; return g; });
    }

    function fileFor(group, day) {
        return group.files.filter(function(f) { return f.day === day; })[0];
    }

    function shownGroups() {
        return state.groups.filter(function(g) { return state.selected.indexOf(g.base) > -1; });
    }

    function renderPicker() {
        var box = el("lv-picks");
        box.innerHTML = "";
        state.groups.forEach(function(g) {
            var label = document.createElement("label");
            label.className = "lv-pick";
            var cb = document.createElement("input");
            cb.type = "checkbox";
            cb.value = g.base;
            cb.checked = state.selected.indexOf(g.base) > -1;
            cb.onchange = function() {
                var bases = [].map.call(box.querySelectorAll("input:checked"), function(c) { return c.value; });
                setSelection(bases);
            };
            var dot = document.createElement("span");
            dot.className = "lv-dot lv-src-" + g.colour;     // the colour its entries are labelled with when merged
            label.appendChild(cb);
            label.appendChild(dot);
            label.appendChild(document.createTextNode(g.label));
            box.appendChild(label);
        });
        [["All", function() { return state.groups.map(function(g) { return g.base; }); }],
         ["None", function() { return []; }]].forEach(function(b) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "lv-btn";
            btn.textContent = b[0];
            btn.onclick = function() { setSelection(b[1]()); renderPicker(); };
            box.appendChild(btn);
        });
    }

    // Days available for the ticked logs: every day any of them has
    function renderDays() {
        var days = { "": true };
        shownGroups().forEach(function(g) {
            g.files.forEach(function(f) { days[f.day || ""] = true; });
        });
        var sel = el("lv-day");
        sel.innerHTML = "";
        Object.keys(days).sort(function(a, b) { return a === "" ? -1 : b === "" ? 1 : (a < b ? 1 : -1); }).forEach(function(d) {
            var o = document.createElement("option");
            o.value = d;
            o.textContent = d || "Today (current)";
            sel.appendChild(o);
        });
        sel.value = state.day || "";
    }

    function setSelection(bases) {
        // keep the logs' own order, whatever order they were ticked in
        state.selected = state.groups.map(function(g) { return g.base; }).filter(function(b) { return bases.indexOf(b) > -1; });
        try { localStorage.setItem("givtcp-log-selection", JSON.stringify(state.selected)); } catch (e) {}
        // keep the chosen day if one of the ticked logs has it, otherwise go back to the current files
        if (state.day && !shownGroups().some(function(g) { return fileFor(g, state.day); })) state.day = null;
        renderDays();
        loadView();
    }

    // The saved selection, or the tab saved by the earlier tabbed viewer, or every log
    function savedSelection() {
        var all = state.groups.map(function(g) { return g.base; });
        try {
            var saved = JSON.parse(localStorage.getItem("givtcp-log-selection"));
            if (Array.isArray(saved)) return saved;
            var tab = localStorage.getItem("givtcp-log-tab");
            if (tab && all.indexOf(tab) > -1) return [tab];
        } catch (e) {}
        return all;
    }

    function loadView() {
        state.sources = shownGroups().map(function(g) {
            var f = fileFor(g, state.day);
            return f && { name: f.name, group: g, mtime: f.mtime, start: 0, size: 0, lines: [], partial: "" };
        }).filter(Boolean);
        el("lv-log").innerHTML = "";
        if (!state.sources.length) {
            render(true);
            return;
        }
        setStatus("Loading…");
        Promise.all(state.sources.map(loadSource)).then(function() {
            render(true);
        }).catch(function(e) {
            setStatus("Could not load the log (" + e.message + ")");
        });
    }

    // ---- Reading files ----
    function fetchRange(name, range) {
        return fetch("logs/" + encodeURIComponent(name), { headers: range ? { Range: range } : {}, cache: "no-store" });
    }

    // Total size from "Content-Range: bytes a-b/total" (or "bytes */total"), or the body length for a whole-file response
    function totalSize(r, text) {
        var cr = r.headers.get("Content-Range");
        var m = cr && cr.match(/\/(\d+)$/);
        return m ? parseInt(m[1], 10) : new Blob([text]).size;
    }

    // A range starting mid-file begins part way through a line: keep that fragment aside (not shown)
    // so "Load earlier" can rejoin it with the rest of the line
    function takeLines(src, text) {
        src.lines = text.split("\n");
        src.partial = src.start > 0 ? src.lines.shift() : "";
    }

    function loadSource(src) {
        return fetchRange(src.name, "bytes=-" + CHUNK).then(function(r) {
            if (r.status === 416) return { r: r, text: "" };           // empty file
            if (!r.ok) throw new Error(src.name + ": " + r.status + " " + r.statusText);
            return r.text().then(function(t) { return { r: r, text: t }; });
        }).then(function(res) {
            src.size = res.r.status === 416 ? 0 : totalSize(res.r, res.text);
            src.start = Math.max(0, src.size - CHUNK);
            takeLines(src, res.text);
        });
    }

    // Read the chunk before what's shown
    function earlierSource(src) {
        if (src.start <= 0) return Promise.resolve();
        var from = Math.max(0, src.start - CHUNK);
        return fetchRange(src.name, "bytes=" + from + "-" + (src.start - 1)).then(function(r) {
            return r.text();
        }).then(function(t) {
            var shown = src.lines;
            src.start = from;
            takeLines(src, t + src.partial);    // the chunk ends where the partial first line began, so this rejoins it
            src.lines = src.lines.concat(shown);
        });
    }

    function loadEarlier() {
        Promise.all(state.sources.map(earlierSource)).then(function() { render(false); });
    }

    // Follow mode: fetch only the bytes added since the last read. Resolves true if there were new lines,
    // or "reload" if the file was rotated or truncated
    function pollSource(src) {
        return fetchRange(src.name, "bytes=" + src.size + "-").then(function(r) {
            if (r.status === 416) {
                // Nothing at or after our position: either no new lines, or the file was rotated and is now
                // shorter than what we've read ("Content-Range: bytes */<size>" gives its current size)
                return totalSize(r, "") < src.size ? "reload" : false;
            }
            return r.text().then(function(t) {
                if (!t) return false;
                var total = totalSize(r, t);
                if (r.status === 200 || total < src.size) return "reload";
                var added = t.split("\n");
                if (src.lines.length) src.lines[src.lines.length - 1] += added.shift();
                src.lines = src.lines.concat(added);
                src.size = total;
                return true;
            });
        }).catch(function() { return false; });
    }

    function poll() {
        if (state.day || !state.sources.length) return;                    // rotated days don't change
        Promise.all(state.sources.map(pollSource)).then(function(results) {
            if (results.indexOf("reload") > -1) loadView();
            else if (results.indexOf(true) > -1) render(el("lv-follow").checked);
        });
    }

    // ---- Rendering ----
    function lineLevel(line, last) {
        var m = line.match(/\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\]/);
        return m ? m[1] : last;             // tracebacks and wrapped lines take the level of the line above
    }

    // Split a source's lines into entries: a timestamped line plus any continuation lines (eg. tracebacks)
    function entries(src) {
        var out = [], cur = null, level = "INFO";
        src.lines.forEach(function(line) {
            if (!line) return;
            var ts = line.match(TIMESTAMP);
            level = lineLevel(line, level);
            if (ts || !cur) {
                cur = { ts: ts ? ts[1] : "", level: level, lines: [line], src: src };
                out.push(cur);
            } else {
                cur.lines.push(line);
            }
        });
        return out;
    }

    // Merge every source's entries by time. Each part-read file only reaches back so far, so start from the
    // latest of their first timestamps - earlier than that, the busier logs would look as if they had gaps
    function mergedEntries() {
        var all = [], cutoff = "";
        state.sources.forEach(function(src, i) {
            var e = entries(src);
            if (src.start > 0 && e.length && e[0].ts > cutoff) cutoff = e[0].ts;
            e.forEach(function(x, j) { x.order = i * 1e7 + j; all.push(x); });
        });
        return all.filter(function(x) { return x.ts && x.ts >= cutoff; })
                  .sort(function(a, b) { return a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : a.order - b.order; });
    }

    function render(scrollToEnd) {
        var box = el("lv-log");
        var minLevel = LEVELS.indexOf(el("lv-level").value);
        var text = el("lv-filter").value.toLowerCase();
        var merged = state.sources.length > 1;
        var list = merged ? mergedEntries() : (state.sources[0] ? entries(state.sources[0]) : []);
        var total = list.length;
        if (list.length > MAX_LINES) list = list.slice(-MAX_LINES);
        var frag = document.createDocumentFragment(), shown = 0;
        list.forEach(function(entry) {
            if (minLevel > 0 && LEVELS.indexOf(entry.level) < minLevel) return;
            if (text && entry.lines.join("\n").toLowerCase().indexOf(text) === -1 &&
                !(merged && entry.src.group.tag.toLowerCase().indexOf(text) > -1)) return;
            entry.lines.forEach(function(line, i) {
                var d = document.createElement("div");
                d.className = "lv-line lv-" + entry.level.toLowerCase();
                if (merged) {
                    var tag = document.createElement("span");
                    tag.className = "lv-src lv-src-" + entry.src.group.colour;
                    tag.textContent = i === 0 ? entry.src.group.tag : "";
                    d.appendChild(tag);
                    d.appendChild(document.createTextNode(line));     // logs are shown as text, never HTML
                } else {
                    d.textContent = line;
                }
                frag.appendChild(d);
            });
            shown++;
        });
        var atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
        var prevHeight = box.scrollHeight, prevTop = box.scrollTop;
        box.innerHTML = "";
        box.appendChild(frag);
        if (scrollToEnd || atBottom) box.scrollTop = box.scrollHeight;
        else box.scrollTop = prevTop + (box.scrollHeight - prevHeight);   // keep place when earlier lines are added

        var truncated = state.sources.some(function(s) { return s.start > 0; });
        el("lv-earlier").disabled = !truncated;
        var dl = el("lv-download");
        if (merged || !state.sources[0]) {
            dl.style.display = "none";
        } else {
            dl.style.display = "";
            dl.href = "logs/" + encodeURIComponent(state.sources[0].name);
            dl.setAttribute("download", state.sources[0].name);
        }
        var bytes = state.sources.reduce(function(n, s) { return n + s.size; }, 0);
        var read = state.sources.reduce(function(n, s) { return n + s.size - s.start; }, 0);
        setStatus(shown + " of " + total + " entries" +
            (merged ? " from " + state.sources.length + " logs" : "") + " · " + formatSize(bytes) +
            (truncated ? " (showing the last " + formatSize(read) + ")" : "") +
            (!merged && state.sources[0] && state.sources[0].mtime ? " · updated " + new Date(state.sources[0].mtime).toLocaleString() : ""));
        if (!state.sources.length) setStatus(state.selected.length ? "No file for this day" : "No logs selected");
        if (!shown) {
            var p = document.createElement("div");
            p.className = "lv-empty";
            p.textContent = !state.selected.length ? "Tick one or more logs above to show them." :
                !state.sources.length ? "None of the ticked logs has a file for this day." :
                total ? "No lines match the filter." : "No log entries.";
            box.appendChild(p);
        }
    }

    function formatSize(b) {
        return b < 1024 ? b + " B" : b < 1048576 ? (b / 1024).toFixed(0) + " KB" : (b / 1048576).toFixed(1) + " MB";
    }
    function setStatus(t) { el("lv-status").textContent = t; }

    function setFollow(on) {
        clearInterval(state.timer);
        state.timer = on ? setInterval(poll, FOLLOW_MS) : null;
        try { localStorage.setItem("givtcp-log-follow", on ? "1" : "0"); } catch (e) {}
    }

    // ---- Start up ----
    el("lv-day").onchange = function() { state.day = this.value || null; loadView(); };
    el("lv-level").onchange = function() { render(false); };
    el("lv-filter").oninput = function() { render(false); };
    el("lv-earlier").onclick = loadEarlier;
    el("lv-refresh").onclick = function() { init(); };
    el("lv-follow").onchange = function() { setFollow(this.checked); };
    try { el("lv-follow").checked = localStorage.getItem("givtcp-log-follow") !== "0"; } catch (e) {}
    setFollow(el("lv-follow").checked);

    function renderPickerAndLoad(bases) {
        setSelection(bases);
        renderPicker();
    }

    function init() {
        fetch("logs/", { cache: "no-store" }).then(function(r) {
            if (!r.ok) throw new Error(r.status + " " + r.statusText);
            return r.json();
        }).then(function(listing) {
            state.groups = groupFiles(listing);
            if (!state.groups.length) { setStatus("No log files found in /config/GivTCP/logs."); return; }
            renderPickerAndLoad(state.selected || savedSelection());
        }).catch(function(e) {
            setStatus("Could not list the log files (" + e.message + ").");
        });
    }
    init();
})();
