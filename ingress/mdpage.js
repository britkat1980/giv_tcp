// Renders a markdown doc into a static ingress page, styled like the readme (pages.css .doc).
// Usage: <div class="doc md" data-md="docs/SETTINGS-GUIDE.md"></div> plus marked.js and this script.
// The Dockerfile copies the .md files next to the pages in the same layout as the repo, so the pages always
// match the repo docs and their relative links and images resolve the same way as on GitHub.
(function() {
    // Links between the docs point at the .md files (repo paths); send them to the matching ingress pages
    var pageFor = {
        "README.md": "readme.html",
        "docs/SETTINGS-GUIDE.md": "settings.html",
        "docs/DATAPOINTS.md": "datapoints.html"
    };
    var pageNames = { "readme.html": "Readme", "settings.html": "Settings Guide", "datapoints.html": "Datapoints" };
    var siteRoot = new URL(".", location.href);

    // GitHub-style heading anchors, so links such as DATAPOINTS.md#ems keep working
    function slug(text, used) {
        var s = text.trim().toLowerCase().replace(/[^\w\- ]+/g, "").replace(/ /g, "-");
        var base = s, n = 1;
        while (used[s]) { s = base + "-" + n++; }
        used[s] = true;
        return s;
    }

    function isRelative(url) {
        return url && !/^([a-z]+:|\/|#)/i.test(url);
    }

    function render(doc, md, mdUrl) {
        var card = document.createElement("div");
        card.className = "card";
        card.innerHTML = marked.parse(md);

        var used = {};
        card.querySelectorAll("h1, h2, h3, h4, h5").forEach(function(h) { h.id = slug(h.textContent, used); });

        // Relative image paths are written relative to the .md file, not the page
        card.querySelectorAll("img[src]").forEach(function(img) {
            var src = img.getAttribute("src");
            if (isRelative(src)) img.src = new URL(src, mdUrl).href;
        });

        card.querySelectorAll("a[href]").forEach(function(a) {
            var href = a.getAttribute("href");
            if (isRelative(href)) {
                var target = new URL(href, mdUrl);
                var repoPath = target.href.indexOf(siteRoot.href) === 0 ? target.pathname.slice(siteRoot.pathname.length) : "";
                var page = pageFor[repoPath];
                if (page) {
                    a.setAttribute("href", page + target.hash);
                    // A link whose text is just the file path reads better as the page name
                    if (a.textContent === href.split("#")[0]) a.textContent = pageNames[page];
                } else {
                    a.setAttribute("href", target.href);
                }
            } else if (/^https?:/.test(href)) {
                a.target = "_blank";
            }
        });

        // Let JSON payloads in table cells wrap after their commas rather than widening the column
        card.querySelectorAll("td code").forEach(function(c) {
            if (c.textContent.indexOf(",") > -1) c.innerHTML = c.innerHTML.replace(/,/g, ",<wbr>");
        });

        // Tables scroll sideways on narrow screens rather than stretching the page
        card.querySelectorAll("table").forEach(function(t) {
            var wrap = document.createElement("div");
            wrap.className = "table-wrap";
            t.parentNode.insertBefore(wrap, t);
            wrap.appendChild(t);
        });

        // Contents from the h2/h3 headings
        var toc = document.createElement("nav");
        toc.className = "card toc";
        toc.innerHTML = '<div class="toc-title">Contents</div><ul></ul>';
        var list = toc.querySelector("ul");
        card.querySelectorAll("h2, h3").forEach(function(h) {
            var li = document.createElement("li");
            if (h.tagName === "H3") li.className = "toc-sub";
            var a = document.createElement("a");
            a.href = "#" + h.id;
            a.textContent = h.textContent;
            li.appendChild(a);
            list.appendChild(li);
        });

        doc.innerHTML = "";
        if (list.children.length > 1) doc.appendChild(toc);
        doc.appendChild(card);

        // The content arrives after load, so jump to any #anchor in the URL now it exists
        if (location.hash) {
            var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
            if (target) target.scrollIntoView();
        }
    }

    document.querySelectorAll(".doc[data-md]").forEach(function(doc) {
        var src = doc.getAttribute("data-md");
        var mdUrl = new URL(src, location.href);
        fetch(mdUrl).then(function(r) {
            if (!r.ok) throw new Error(r.status + " " + r.statusText);
            return r.text();
        }).then(function(md) {
            render(doc, md, mdUrl);
        }).catch(function(e) {
            doc.innerHTML = '<div class="card"><p>Could not load ' + src + " (" + e.message + ").</p></div>";
        });
    });
})();
