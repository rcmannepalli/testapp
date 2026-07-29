#!/usr/bin/env python3
"""Consent UI — a tiny web front-end for the opt-in/opt-out registry.

The browser companion to consent.py. A person opens the page, sees their own
consent status and exactly what is stored about them, and can **opt in** or
**opt out** (opt-out deletes their stored data). It writes through the same
id-keyed store.py, so the CLI and the UI are the same source of truth.

Stdlib only (http.server) — no web framework, no dependency.

    python consent_server.py --db team.db          # http://127.0.0.1:8000
    python consent_server.py --port 8080

Identity: this prototype lets you pick who you are from the known roster, which
stands in for single-sign-on. IN PRODUCTION this screen is behind Slack OAuth so
a person can only ever see and act on their own record — never anyone else's.
Run `consent.py --import <transcript>` (or score a run) first so there are
identities to show.
"""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import store
from mirror import PALETTE, esc

DB_PATH = store.DEFAULT_DB
P = PALETTE


def page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:{P['bg']}; color:{P['ink']};
    font:16px/1.55 "Iowan Old Style", Georgia, serif; }}
  .wrap {{ max-width:620px; margin:0 auto; padding:48px 24px 80px; }}
  h1 {{ font-size:28px; margin:0 0 6px; }}
  .sub {{ color:{P['muted']}; font-style:italic; margin:0 0 28px; }}
  .card {{ background:{P['card']}; border:1px solid {P['line']}; border-radius:12px;
    padding:22px 24px; margin-bottom:18px; }}
  .status {{ font-size:20px; font-weight:700; }}
  .in {{ color:{P['good']}; }} .out {{ color:{P['warn']}; }} .none {{ color:{P['muted']}; }}
  .muted {{ color:{P['muted']}; }}
  ul {{ padding-left:20px; }} li {{ margin:4px 0; }}
  form {{ display:inline; }}
  button {{ font:inherit; border:none; border-radius:8px; padding:11px 20px;
    cursor:pointer; font-weight:600; }}
  .primary {{ background:{P['good']}; color:#fff; }}
  .danger {{ background:{P['card']}; color:{P['warn']}; border:1px solid {P['warn']}; }}
  .banner {{ border-radius:8px; padding:12px 16px; margin-bottom:20px; font-size:15px; }}
  .banner.ok {{ background:#e8f3ea; border:1px solid {P['good']}; }}
  .banner.gone {{ background:#f6ece0; border:1px solid {P['warn']}; }}
  a {{ color:{P['accent']}; }}
  .roster a {{ display:block; padding:10px 14px; border:1px solid {P['line']};
    border-radius:8px; margin:6px 0; text-decoration:none; color:{P['ink']}; }}
  .note {{ font-size:13px; color:{P['muted']}; border-left:3px solid {P['line']};
    padding:6px 0 6px 14px; margin-top:24px; }}
</style></head>
<body><div class="wrap">{body}</div></body></html>"""


def roster_page(conn) -> str:
    ids = store.all_identities(conn)
    if not ids:
        body = ('<h1>Consent</h1><div class="card">No people are known yet. '
                'Import a channel first:<br><code>python consent.py --import '
                '&lt;transcript.json&gt;</code></div>')
        return page("Consent", body)
    links = "".join(
        f'<a href="/?me={esc(aid)}">{esc(name)} <span class="muted">({esc(aid)})</span></a>'
        for aid, name in sorted(ids.items(), key=lambda kv: kv[1])
    )
    body = (
        '<h1>Who are you?</h1>'
        '<p class="sub">Pick yourself to review your consent. '
        '(In production this is your Slack sign-in.)</p>'
        f'<div class="card roster">{links}</div>'
    )
    return page("Consent", body)


def person_page(conn, aid: str, done: str = "") -> str:
    name = store.display_name(conn, aid)
    status = store.get_consent(conn, aid)
    findings = store.person_findings(conn, aid)
    runs = len(store.person_timeline(conn, aid))

    banner = ""
    if done == "in":
        banner = '<div class="banner ok">You’re opted in. You can opt out any time.</div>'
    elif done == "out":
        banner = ('<div class="banner gone">You’re opted out and your stored '
                  'feedback has been deleted.</div>')

    label = {"in": ('opted IN', 'in'), "out": ('opted OUT', 'out'),
             None: ('no decision yet', 'none')}[status]
    stored = (f'{len(findings)} stored observation(s) across {runs} run(s)'
              if findings else 'nothing stored about you')

    body = f"""
{banner}
<h1>{esc(name)}</h1>
<p class="sub">{esc(aid)} · your consent for Respect &amp; Listening feedback</p>

<div class="card">
  <div class="status {label[1]}">You are {esc(label[0])}.</div>
  <p class="muted" style="margin:8px 0 0">Currently {esc(stored)}.</p>
</div>

<div class="card">
  <p><b>What opting in means</b></p>
  <ul>
    <li>Your messages in connected channels may be scored for respect &amp; listening.</li>
    <li>You see your own feedback first, in your private mirror — with your own words.</li>
    <li>The org only ever sees team aggregates, never your name or quotes.</li>
    <li>Opting out is free, has no penalty, and deletes what’s already stored about you.</li>
  </ul>
  <div style="margin-top:16px">
    <form method="POST" action="/opt-in"><input type="hidden" name="me" value="{esc(aid)}">
      <button class="primary" type="submit">Opt in</button></form>
    <form method="POST" action="/opt-out" onsubmit="return confirm('Opt out and permanently delete your {len(findings)} stored observation(s)?');">
      <input type="hidden" name="me" value="{esc(aid)}">
      <button class="danger" type="submit">Opt out &amp; delete my data</button></form>
  </div>
</div>

<p class="muted"><a href="/">← back</a></p>
<div class="note">Prototype: identity is picked from a roster. In production this
screen sits behind Slack sign-in, so you can only ever act on your own record.</div>
"""
    return page(f"Consent — {name}", body)


class Handler(BaseHTTPRequestHandler):
    def _send(self, html: str, code: int = 200):
        data = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _known(self, conn, aid: str) -> bool:
        return bool(aid) and store.is_known(conn, aid)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self._send(page("Not found", "<h1>404</h1>"), 404)
            return
        q = parse_qs(parsed.query)
        me = (q.get("me") or [""])[0]
        done = (q.get("done") or [""])[0]
        conn = store.connect(DB_PATH)
        try:
            if me and self._known(conn, me):
                self._send(person_page(conn, me, done))
            else:
                self._send(roster_page(conn))
        finally:
            conn.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        me = (form.get("me") or [""])[0]
        conn = store.connect(DB_PATH)
        try:
            if not self._known(conn, me):
                self._send(page("Unknown", "<h1>Unknown person</h1>"), 400)
                return
            if parsed.path == "/opt-in":
                store.set_consent(conn, me, "in")
                self._redirect(f"/?me={me}&done=in")
            elif parsed.path == "/opt-out":
                store.purge_person(conn, me)
                store.set_consent(conn, me, "out")
                self._redirect(f"/?me={me}&done=out")
            else:
                self._send(page("Not found", "<h1>404</h1>"), 404)
        finally:
            conn.close()

    def log_message(self, *args):
        pass  # quiet by default


def main() -> None:
    global DB_PATH
    args = sys.argv[1:]
    host, port = "127.0.0.1", 8000
    if "--db" in args:
        DB_PATH = args[args.index("--db") + 1]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if "--host" in args:
        host = args[args.index("--host") + 1]

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"  consent UI on http://{host}:{port}  (db: {DB_PATH})")
    print("  Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")


if __name__ == "__main__":
    main()
