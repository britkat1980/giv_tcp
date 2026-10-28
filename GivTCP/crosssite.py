"""Refuse requests that another website's page makes through a visitor's browser. Browsers send Sec-Fetch-Site with
every request, as cross-site when the page making it is on another site. Predbat, Home Assistant's rest_command and
curl don't send it, so they aren't affected, and nor are GivTCP's own pages (same-origin, also through HA ingress)
or the web dashboard on port 3000 (same-site)"""
from flask import request, Response

def refuse_cross_site(app, allowed=frozenset()):
    """Refuse cross-site requests to every route of app except the paths in allowed (read-only data)"""
    @app.before_request
    def _refuseCrossSite():
        if request.headers.get('Sec-Fetch-Site','').lower()=='cross-site' and request.path not in allowed:
            return Response('{"result":"Error: cross-site requests are refused"}', status=403, mimetype='application/json')
