// Loads header.html (the menu) into #includeHead on every page, and runs its script, as jQuery's load() did
(function() {
    function load() {
        var box = document.getElementById("includeHead");
        if (!box) return;
        // A unique URL, so a cached (stale) header is never used
        fetch("header.html?_=" + Date.now(), { cache: "no-store" }).then(function(r) {
            return r.text();
        }).then(function(html) {
            box.innerHTML = html;
            // Scripts added with innerHTML don't run, so replace each with a new one that does
            box.querySelectorAll("script").forEach(function(old) {
                var s = document.createElement("script");
                s.textContent = old.textContent;
                old.replaceWith(s);
            });
        }).catch(function() {});
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
    else load();
})();
