#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Consent UI — opt-in/opt-out registry with Sign in with Slack (OIDC SSO).

The browser companion to consent.py. A person signs in with Slack, sees their
own consent status and exactly what is stored about them, and can **opt in** or
**opt out** (opt-out deletes their stored data). It writes through the same
id-keyed store.py, so the CLI and the UI are the same source of truth.

Stdlib only (http.server + urllib) — no web framework, no JWT/crypto dependency.

Authentication — "Sign in with Slack" (OpenID Connect on OAuth 2.0):
  1. /login redirects to Slack's consent screen (state = CSRF guard).
  2. Slack redirects back to /oauth/callback with a code.
  3. We exchange the code server-to-server for an access token, then call Slack's
     userInfo endpoint — both over TLS, straight from Slack — to get the verified
     Slack user id. That id IS the author_id the consent registry keys on.
  4. A session cookie binds the browser to that id. Opt-in/opt-out act on the
     SESSION's id only, so a person can never touch anyone else's record.

Configure (reuse your existing Slack app; add the `openid,email,profile` scopes
under OAuth & Permissions → User Token Scopes, and register the redirect URL):
    export SLACK_CLIENT_ID=...        # api.slack.com/apps → Basic Information
    export SLACK_CLIENT_SECRET=...
    export SLACK_REDIRECT_URI=http://localhost:8000/oauth/callback   # optional
    python consent_server.py --db team.db

Offline / no Slack app:
    python consent_server.py --dev    # roster picker stands in for sign-in
"""
import json
import os
import secrets
import sys
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import store
from mirror import PALETTE, esc

DB_PATH = store.DEFAULT_DB
P = PALETTE

# --- Sign in with Slack (OIDC) configuration ---------------------------------
AUTHORIZE_URL = "https://slack.com/openid/connect/authorize"
TOKEN_URL = "https://slack.com/api/openid.connect.token"
USERINFO_URL = "https://slack.com/api/openid.connect.userInfo"
SLACK_USER_ID_CLAIM = "https://slack.com/user_id"

CLIENT_ID = os.environ.get("SLACK_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET", "")
REDIRECT_URI = ""   # resolved in main()
DEV_MODE = False    # roster picker instead of real SSO

# In-memory session + pending-login stores (a prototype; a real deploy uses a
# signed cookie / shared session store). session id -> author_id; state -> True.
SESSIONS: dict[str, str] = {}
PENDING: dict[str, bool] = {}


# --- HTML --------------------------------------------------------------------


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
  button, .btn {{ font:inherit; border:none; border-radius:8px; padding:11px 20px;
    cursor:pointer; font-weight:600; text-decoration:none; display:inline-block; }}
  .primary {{ background:{P['good']}; color:#fff; }}
  .danger {{ background:{P['card']}; color:{P['warn']}; border:1px solid {P['warn']}; }}
  .slack {{ background:#4A154B; color:#fff; font-size:17px; padding:13px 22px; }}
  .banner {{ border-radius:8px; padding:12px 16px; margin-bottom:20px; font-size:15px; }}
  .banner.ok {{ background:#e8f3ea; border:1px solid {P['good']}; }}
  .banner.gone {{ background:#f6ece0; border:1px solid {P['warn']}; }}
  a {{ color:{P['accent']}; }}
  .roster a {{ display:block; padding:10px 14px; border:1px solid {P['line']};
    border-radius:8px; margin:6px 0; text-decoration:none; color:{P['ink']}; }}
  .who {{ float:right; font-size:13px; color:{P['muted']}; }}
  .note {{ font-size:13px; color:{P['muted']}; border-left:3px solid {P['line']};
    padding:6px 0 6px 14px; margin-top:24px; }}
</style></head>
<body><div class="wrap">{body}</div></body></html>"""


def login_page() -> str:
    body = (
        '<h1>Respect &amp; Listening — your consent</h1>'
        '<p class="sub">Sign in so we know it’s you. You’ll only ever see and '
        'control your own record.</p>'
        '<div class="card"><a class="btn slack" href="/login">Sign in with Slack</a></div>'
        '<div class="note">Sign in with Slack uses OpenID Connect: Slack verifies '
        'who you are and tells us your user id — we never see your password.</div>'
    )
    return page("Sign in", body)


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
        '<h1>Who are you? <span class="muted">(dev)</span></h1>'
        '<p class="sub">Dev mode — pick yourself. Real deploys use Sign in with Slack.</p>'
        f'<div class="card roster">{links}</div>'
    )
    return page("Consent", body)


def person_page(conn, aid: str, done: str = "", signed_in: bool = False) -> str:
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

    who = ('<div class="who">signed in as ' + esc(name) + ' · <a href="/logout">sign out</a></div>'
           if signed_in else '')
    label = {"in": ('opted IN', 'in'), "out": ('opted OUT', 'out'),
             None: ('no decision yet', 'none')}[status]
    stored = (f'{len(findings)} stored observation(s) across {runs} run(s)'
              if findings else 'nothing stored about you')

    body = f"""
{who}{banner}
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
    <form method="POST" action="/opt-in"><button class="primary" type="submit">Opt in</button></form>
    <form method="POST" action="/opt-out" onsubmit="return confirm('Opt out and permanently delete your {len(findings)} stored observation(s)?');">
      <button class="danger" type="submit">Opt out &amp; delete my data</button></form>
  </div>
</div>
<div class="note">Opt-in / opt-out act on your signed-in identity only — the
server ignores anything the page tries to submit about who you are.</div>
"""
    return page(f"Consent — {name}", body)


# --- Slack OIDC helpers ------------------------------------------------------


def authorize_url(state: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code",
        "scope": "openid email profile",
        "client_id": CLIENT_ID,
        "state": state,
        "redirect_uri": REDIRECT_URI,
    })


def _post_json(url: str, data: dict) -> dict:
    req = Request(url, data=urlencode(data).encode(), method="POST")
    with urlopen(req, timeout=30) as resp:
        return json.load(resp)


def exchange_code(code: str) -> str:
    """Trade an auth code for an access token (server-to-server, over TLS)."""
    res = _post_json(TOKEN_URL, {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    })
    if not res.get("access_token"):
        raise RuntimeError(f"token exchange failed: {res.get('error', res)}")
    return res["access_token"]


def fetch_identity(access_token: str) -> tuple[str, str]:
    """Return (verified Slack user id, display name) from the userInfo endpoint."""
    req = Request(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    with urlopen(req, timeout=30) as resp:
        info = json.load(resp)
    uid = info.get(SLACK_USER_ID_CLAIM)
    if not uid:
        raise RuntimeError(f"userInfo missing user id: {info.get('error', info)}")
    name = info.get("name") or info.get("email") or uid
    return uid, name


# --- HTTP handler ------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def _send(self, html: str, code: int = 200, cookie: str | None = None):
        data = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str, cookie: str | None = None):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _session_id(self) -> str | None:
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = SimpleCookie()
        jar.load(raw)
        sid = jar["sid"].value if "sid" in jar else None
        return SESSIONS.get(sid) if sid else None

    # --- GET ---
    def do_GET(self):
        parsed = urlparse(self.path)
        path, q = parsed.path, parse_qs(parsed.query)
        if path == "/login":
            return self._start_login()
        if path == "/oauth/callback":
            return self._finish_login(q)
        if path == "/logout":
            return self._logout()
        if path != "/":
            return self._send(page("Not found", "<h1>404</h1>"), 404)

        conn = store.connect(DB_PATH)
        try:
            if DEV_MODE:
                me = (q.get("me") or [""])[0]
                if me and store.is_known(conn, me):
                    self._send(person_page(conn, me, (q.get("done") or [""])[0]))
                else:
                    self._send(roster_page(conn))
            else:
                me = self._session_id()
                if me:
                    self._send(person_page(conn, me, (q.get("done") or [""])[0], signed_in=True))
                else:
                    self._send(login_page())
        finally:
            conn.close()

    def _start_login(self):
        if DEV_MODE:
            return self._redirect("/")
        state = secrets.token_urlsafe(24)
        PENDING[state] = True
        self._redirect(authorize_url(state))

    def _finish_login(self, q: dict):
        state = (q.get("state") or [""])[0]
        code = (q.get("code") or [""])[0]
        if not code or not PENDING.pop(state, False):
            return self._send(page("Sign-in failed",
                "<h1>Sign-in failed</h1><p>Invalid or expired request. "
                "<a href='/'>Try again</a>.</p>"), 400)
        try:
            uid, name = fetch_identity(exchange_code(code))
        except Exception as e:  # network / Slack error — show, don't crash
            return self._send(page("Sign-in failed",
                f"<h1>Sign-in failed</h1><p>{esc(str(e))}</p><p><a href='/'>Back</a></p>"), 502)
        conn = store.connect(DB_PATH)
        try:
            store.register_identities(conn, {uid: name}, verified=True)
        finally:
            conn.close()
        sid = secrets.token_urlsafe(32)
        SESSIONS[sid] = uid
        self._redirect("/", cookie=f"sid={sid}; HttpOnly; Path=/; SameSite=Lax")

    def _logout(self):
        raw = self.headers.get("Cookie")
        if raw:
            jar = SimpleCookie()
            jar.load(raw)
            if "sid" in jar:
                SESSIONS.pop(jar["sid"].value, None)
        self._redirect("/", cookie="sid=; Max-Age=0; Path=/")

    # --- POST (opt-in / opt-out) ---
    def do_POST(self):
        path = urlparse(self.path).path
        # Identity comes from the authenticated session (SSO) — never from the
        # request body — so a person can only ever act on their own record.
        if DEV_MODE:
            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            me = (form.get("me") or [""])[0]
        else:
            me = self._session_id()
            if not me:
                return self._redirect("/")

        conn = store.connect(DB_PATH)
        try:
            if not me or not store.is_known(conn, me):
                return self._send(page("Unknown", "<h1>Unknown person</h1>"), 400)
            if path == "/opt-in":
                store.set_consent(conn, me, "in")
                self._redirect("/?done=in" if not DEV_MODE else f"/?me={me}&done=in")
            elif path == "/opt-out":
                store.purge_person(conn, me)
                store.set_consent(conn, me, "out")
                self._redirect("/?done=out" if not DEV_MODE else f"/?me={me}&done=out")
            else:
                self._send(page("Not found", "<h1>404</h1>"), 404)
        finally:
            conn.close()

    def log_message(self, *args):
        pass


def main() -> None:
    global DB_PATH, REDIRECT_URI, DEV_MODE
    args = sys.argv[1:]
    host, port = "127.0.0.1", 8000
    if "--db" in args:
        DB_PATH = args[args.index("--db") + 1]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if "--host" in args:
        host = args[args.index("--host") + 1]

    REDIRECT_URI = os.environ.get(
        "SLACK_REDIRECT_URI", f"http://{host}:{port}/oauth/callback"
    )
    DEV_MODE = "--dev" in args or not (CLIENT_ID and CLIENT_SECRET)

    mode = "DEV roster (no real sign-in)" if DEV_MODE else "Sign in with Slack (OIDC)"
    if DEV_MODE and "--dev" not in args:
        print("  ! SLACK_CLIENT_ID/SECRET not set — falling back to --dev roster mode.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"  consent UI on http://{host}:{port}  (db: {DB_PATH})")
    print(f"  auth: {mode}")
    if not DEV_MODE:
        print(f"  redirect URI (register this in your Slack app): {REDIRECT_URI}")
    print("  Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")


if __name__ == "__main__":
    main()
