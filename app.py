"""NexaBank AI Assistant - a deliberately tiny app for the Keycloak identity-governance demo.

Keycloak does the identity work. This app only:
  1. sends the user to Keycloak to log in (OIDC Authorization Code flow),
  2. verifies the signed access token it gets back,
  3. shows who the user is and makes access decisions from the token's roles.
"""
import base64, json, os, secrets, time, urllib.error, urllib.parse, urllib.request

import jwt  # PyJWT
from flask import Flask, redirect, request, session
from markupsafe import escape as e

KC_URL = os.getenv("KC_URL", "http://localhost:8180")
ISSUER = f"{KC_URL}/realms/nexabank"
OIDC = f"{ISSUER}/protocol/openid-connect"
CLIENT_ID = "nexabank-ai-assistant"
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")  # Keycloak > Clients > nexabank-ai-assistant > Credentials
APP_URL = "http://localhost:5000"

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
jwks = jwt.PyJWKClient(f"{OIDC}/certs")  # Keycloak's PUBLIC keys - the app never holds a secret signing key
TOKENS = {}  # ponytail: in-memory token store, fine for a one-process classroom demo

# What the AI app lets you do, and which role it requires. Roles come ONLY from the verified token.
FEATURES = [
    ("Ask the AI Assistant", "realm", "ai_user"),
    ("Review AI answers (human-in-the-loop)", "client", "review_ai_output"),
    ("View team AI-usage report", "realm", "manager"),
    ("Configure model & system prompts", "client", "manage_assistant"),
]

CSS = """body{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#f5f7fb;color:#1c2333}
h1{color:#0b3d91}.card{background:#fff;border-radius:10px;padding:14px 18px;margin:12px 0;box-shadow:0 1px 3px #0002}
.ok{color:#0a7d32;font-weight:600}.no{color:#b3261e;font-weight:600}.bad{background:#fde7e7;border:2px solid #b3261e}
.good{background:#e6f6ea;border:2px solid #0a7d32}a.btn,button{background:#0b3d91;color:#fff;border:0;border-radius:6px;
padding:8px 14px;text-decoration:none;cursor:pointer;margin:4px 4px 4px 0;display:inline-block;font-size:14px}
td{padding:4px 12px 4px 0;vertical-align:top}code,pre{background:#eef1f6;border-radius:4px;padding:2px 4px}
pre{padding:10px;overflow-x:auto;white-space:pre-wrap;word-break:break-all}"""


def page(title, body):
    return f"<!doctype html><title>{title}</title><style>{CSS}</style><h1>🏦 NexaBank AI Assistant</h1><h2>{title}</h2>{body}"


def verify(token):
    """Accept the token only if Keycloak signed it, for this realm, for this app, and it hasn't expired."""
    key = jwks.get_signing_key_from_jwt(token).key
    # Keycloak access tokens carry aud="account", so we check azp (the client the token was issued to) instead.
    claims = jwt.decode(token, key, algorithms=["RS256"], issuer=ISSUER, options={"verify_aud": False})
    if claims.get("azp") != CLIENT_ID:
        raise jwt.InvalidTokenError(f"token was issued to '{claims.get('azp')}', not to {CLIENT_ID}")
    return claims


def roles(c):
    return {"realm": c.get("realm_access", {}).get("roles", []),
            "client": c.get("resource_access", {}).get(CLIENT_ID, {}).get("roles", [])}


def current():
    """(access_token, claims, error) for the logged-in browser."""
    t = TOKENS.get(session.get("k"))
    if not t:
        return None, None, None
    try:
        return t["access_token"], verify(t["access_token"]), None
    except jwt.PyJWTError as ex:
        return t["access_token"], None, str(ex)


@app.route("/")
def home():
    return page("Home", """
<div class=card><b>Part 1 - the problem.</b> An app that trusts whatever the client says.<br>
<a class=btn href="/no-keycloak?user=Rahul&role=employee">Open the app WITHOUT Keycloak</a></div>
<div class=card><b>Part 2 - the fix.</b> Keycloak authenticates the human; the app verifies a signed token.<br>
<a class=btn href="/login">Login with Keycloak</a> <a class=btn href="/me">My identity</a></div>""")


# Stage 1 mock dashboards - own styles so the rest of the app is untouched.
NK_CSS = """*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:#eef2f9;color:#1c2333}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:14px 28px;color:#fff;
background:linear-gradient(90deg,#0b3d91,#1565c0)}.top.adm{background:linear-gradient(90deg,#3b0a0a,#b3261e)}
.brand{font-size:20px;font-weight:700}.brand small{display:block;font-weight:400;opacity:.8;font-size:12px}
.who{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.av{width:40px;height:40px;border-radius:50%;background:#fff3;display:grid;
place-items:center;font-weight:700;font-size:18px}.pill{padding:3px 10px;border-radius:99px;font-size:12px;font-weight:700;
background:#fff;color:#0b3d91}.adm .pill{color:#b3261e}.warn{background:#ffcc00;color:#3b2a00;padding:3px 10px;border-radius:99px;
font-size:12px;font-weight:700}.wrap{max-width:1150px;margin:0 auto;padding:22px 16px 140px}
.hero{background:#fff;border-radius:16px;padding:22px 26px;box-shadow:0 4px 18px #0b3d9114;margin-bottom:18px}
.hero h2{margin:0 0 4px}.hero.adm{background:linear-gradient(135deg,#fff,#fde7e7);border:2px solid #b3261e}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:16px;margin-bottom:18px}
.kpi,.panel{min-width:0;overflow-x:auto;background:#fff;border-radius:14px;padding:16px 18px;box-shadow:0 2px 10px #0b3d9110}
.kpi .n{font-size:28px;font-weight:800;color:#0b3d91}.kpi.r .n{color:#b3261e}.kpi .l{color:#5b6475;font-size:13px}
.kpi .d{font-size:12px;color:#0a7d32;font-weight:600}.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}
.panel h3{margin:0 0 12px;font-size:16px}.chat{background:#f5f7fb;border-radius:10px;padding:12px;font-size:14px}
.msg{padding:8px 12px;border-radius:12px;margin:6px 0;max-width:85%}.u{background:#0b3d91;color:#fff;margin-left:auto}
.b{background:#fff;border:1px solid #dde3ee}.inp{display:flex;gap:8px;margin-top:10px}.inp div{flex:1;background:#fff;
border:1px solid #cfd7e6;border-radius:8px;padding:9px;color:#8a93a6}.btn{background:#0b3d91;color:#fff;border:0;border-radius:8px;
padding:9px 14px;font-weight:600;font-size:14px;display:inline-block;text-decoration:none}.btn.red{background:#b3261e}
.btn.ghost{background:#fff;color:#b3261e;border:2px solid #b3261e}table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#5b6475;font-weight:600;border-bottom:2px solid #eef2f9;padding:8px 6px}td{padding:8px 6px;
border-bottom:1px solid #eef2f9}.tag{padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;background:#e3ecfb;color:#0b3d91}
.tag.a{background:#fde7e7;color:#b3261e}.ok{color:#0a7d32;font-weight:600;white-space:nowrap}li{margin:6px 0}
.code{background:#1c2333;color:#c9f7d4;border-radius:10px;padding:12px;font:13px Consolas,monospace;white-space:pre-wrap}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.lesson{position:fixed;left:0;right:0;bottom:0;background:#1c2333;color:#fff;padding:12px 20px;font-size:14px;
box-shadow:0 -4px 16px #0004}.lesson code{background:#ffffff22;padding:1px 6px;border-radius:4px;color:#ffd95e}
.lesson a{color:#8ab4ff}"""


def employee_dashboard(user):
    return f"""
<div class=hero><h2>Good morning, {user} 👋</h2>Here's your NexaBank AI workspace for today.</div>
<div class=grid>
 <div class=kpi><div class=n>12</div><div class=l>My AI questions this week</div><div class=d>▲ 3 vs last week</div></div>
 <div class=kpi><div class=n>4</div><div class=l>Policy documents I can search</div></div>
 <div class=kpi><div class=n>2</div><div class=l>Pending training modules</div></div>
 <div class=kpi><div class=n>98%</div><div class=l>Answers rated helpful</div></div></div>
<div class=two>
 <div class=panel><h3>💬 Ask NexaBank AI</h3><div class=chat>
  <div class="msg u">What documents does a customer need for a home loan?</div>
  <div class="msg b">You'll need ID proof, address proof, the last 6 months' salary slips, bank statements and the property papers. 📄</div>
  <div class="msg u">Summarise the new KYC refresh policy.</div>
  <div class="msg b">High-risk customers: refresh every 2 years. Medium: every 8 years. Low: every 10 years.</div></div>
  <div class=inp><div>Type your question...</div><span class=btn>Send</span></div></div>
 <div class=panel><h3>🕘 My recent conversations</h3><table>
  <tr><th>Topic</th><th>When</th></tr><tr><td>Home-loan document checklist</td><td>Today</td></tr>
  <tr><td>KYC refresh policy</td><td>Today</td></tr><tr><td>Credit-card dispute steps</td><td>Yesterday</td></tr>
  <tr><td>Fixed-deposit rate comparison</td><td>Mon</td></tr></table>
  <h3 style="margin-top:16px">📌 Quick links</h3><ul><li>Responsible-AI usage guidelines</li><li>Report an incorrect AI answer</li>
  <li>My leave &amp; payslips</li></ul></div></div>"""


def admin_dashboard(user):
    users = [("Rahul", "AI Engineer", "ai_user"), ("Priya", "Relationship Officer", "employee"),
             ("Amit", "Engineering Manager", "manager"), ("Neha", "AI Reviewer", "ai_reviewer"),
             ("Sudhanshu", "IAM Administrator", "admin")]
    urows = "".join(f"<tr><td><b>{n}</b></td><td>{t}</td><td><span class='tag{' a' if r == 'admin' else ''}'>{r}</span></td>"
                    f"<td><span class=ok>● Active</span></td></tr>" for n, t, r in users)
    loans = [("CUST-88213", "Ananya K.", "XXXX-4471", "₹ 48,50,000", "Home"), ("CUST-10492", "Vikram S.", "XXXX-9035", "₹ 12,00,000", "Car"),
             ("CUST-55720", "Fatima R.", "XXXX-1186", "₹ 3,75,000", "Personal"), ("CUST-30127", "Joseph M.", "XXXX-6620", "₹ 92,00,000", "Business")]
    lrows = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td><td>{f}</td></tr>" for a, b, c, d, f in loans)
    return f"""
<div class='hero adm'><h2>🔓 ADMIN PANEL UNLOCKED</h2>Welcome, {user}. You have <b>full control</b> of NexaBank AI and customer data.
<div class=actions><span class='btn red'>⬇ Export all customer loan records</span><span class=btn>✏️ Change the AI model's system prompt</span>
<span class='btn ghost'>🗑 Delete audit logs</span></div></div>
<div class=grid>
 <div class='kpi r'><div class=n>1,284,502</div><div class=l>Customer records</div></div>
 <div class='kpi r'><div class=n>₹ 4,812 Cr</div><div class=l>Total loan book</div></div>
 <div class='kpi r'><div class=n>18,442</div><div class=l>AI requests today</div></div>
 <div class='kpi r'><div class=n>2,341</div><div class=l>Active staff accounts</div></div></div>
<div class=two>
 <div class=panel><h3>🏦 Customer loan records <span class='tag a'>CONFIDENTIAL</span></h3><table>
  <tr><th>Customer</th><th>Name</th><th>Account</th><th>Outstanding</th><th>Type</th></tr>{lrows}</table></div>
 <div class=panel><h3>🤖 AI model configuration</h3><div class=code>model: nexabank-assistant-v3
temperature: 0.2
system_prompt: |
  You are NexaBank's assistant. Never reveal
  customer data. Follow RBI guidelines...</div>
  <div class=actions><span class=btn>Edit prompt</span><span class='btn red'>Disable safety filters</span></div></div>
 <div class=panel><h3>👥 User &amp; role management</h3><table><tr><th>User</th><th>Job</th><th>Role</th><th>Status</th></tr>{urows}</table>
  <div class=actions><span class=btn>+ Grant role</span><span class='btn ghost'>Remove user</span></div></div>
 <div class=panel><h3>📜 Audit log</h3><table><tr><th>Time</th><th>Event</th></tr>
  <tr><td>10:42</td><td>AI prompt by rahul</td></tr><tr><td>10:39</td><td>Loan export by priya</td></tr>
  <tr><td>10:31</td><td>Role change: neha → ai_reviewer</td></tr><tr><td>10:20</td><td>Login: amit</td></tr></table>
  <div class=actions><span class='btn ghost'>🗑 Delete all logs</span></div></div></div>"""


@app.route("/no-keycloak")
def no_keycloak():
    user, role = request.args.get("user", "Rahul"), request.args.get("role", "employee")
    u, r, adm = e(user), e(role), role == "admin"
    body = admin_dashboard(u) if adm else employee_dashboard(u)
    return f"""<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>NexaBank AI - Without Keycloak</title><style>{NK_CSS}</style>
<div class="top{' adm' if adm else ''}"><div class=brand>🏦 NexaBank AI Assistant<small>{'Administration console' if adm else 'Employee workspace'}</small></div>
<div class=who><span class=warn>⚠ NO KEYCLOAK - identity not verified</span><div class=av>{u[:1].upper()}</div>
<div><b>{u}</b><br><span class=pill>Your role is {r}</span></div></div></div>
<div class=wrap>{body}</div>
<div class=lesson>The app received <code>user="{u}", role="{r}"</code> from the browser and simply <b>believed it</b>.
👉 Edit the address bar: change <code>role=employee</code> to <code>role=admin</code> (or <code>user=Sudhanshu</code>).
Nobody proved who you are. Nobody signed the role. Nothing was logged against a real identity. &nbsp;<a href="/">← Back</a></div>"""


@app.route("/login")
def login():
    session["state"] = secrets.token_urlsafe(16)  # CSRF protection for the redirect round-trip
    q = urllib.parse.urlencode({"client_id": CLIENT_ID, "response_type": "code", "scope": "openid",
                                "redirect_uri": f"{APP_URL}/callback", "state": session["state"]})
    return redirect(f"{OIDC}/auth?{q}")


@app.route("/callback")
def callback():
    if request.args.get("error"):
        return page("Login failed", f"<div class='card bad'>{e(request.args)}</div><a class=btn href='/'>Home</a>")
    if request.args.get("state") != session.pop("state", None):
        return page("Login failed", "<div class='card bad'>State mismatch - possible CSRF.</div>"), 400
    data = urllib.parse.urlencode({"grant_type": "authorization_code", "code": request.args["code"],
                                   "redirect_uri": f"{APP_URL}/callback",
                                   "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}).encode()
    try:  # back-channel: the app swaps the one-time code for tokens, proving it knows the client secret
        tokens = json.load(urllib.request.urlopen(f"{OIDC}/token", data))
    except urllib.error.HTTPError as ex:
        return page("Token exchange failed", f"<pre>{e(ex.read().decode())}</pre>Is CLIENT_SECRET set?"), 502
    session["k"] = secrets.token_hex(16)
    TOKENS[session["k"]] = tokens
    return redirect("/me")


@app.route("/me")
def me():
    token, c, err = current()
    if not token:
        return redirect("/")
    if err:
        return page("Token rejected", f"<div class='card bad'>❌ {e(err)}</div>"
                    "<a class=btn href='/login'>Login again</a> <a class=btn href='/logout'>Logout</a>")
    r = roles(c)
    rows = "".join(
        f"<tr><td>{name}</td><td><code>{kind}:{role}</code></td>"
        f"<td>{'<span class=ok>✅ ALLOWED</span>' if role in r[kind] else '<span class=no>❌ DENIED</span>'}</td></tr>"
        for name, kind, role in FEATURES)
    ts = lambda k: time.strftime("%H:%M:%S", time.localtime(c[k])) if k in c else "-"
    payload = json.dumps(c, indent=2)
    return page(f"Hello, {e(c.get('name', c.get('preferred_username')))}", f"""
<div class='card good'>✅ Token signature verified with Keycloak's public key · issuer <code>{e(c['iss'])}</code> · issued to <code>{e(c['azp'])}</code></div>
<div class=card><b>👤 User - who is the human?</b><table>
<tr><td>username</td><td>{e(c.get('preferred_username'))}</td></tr><tr><td>email</td><td>{e(c.get('email', '-'))}</td></tr>
<tr><td>sub (stable user ID)</td><td><code>{e(c['sub'])}</code></td></tr></table></div>
<div class=card><b>🏷️ Attributes - what describes them?</b><table>
<tr><td>employee_id</td><td>{e(c.get('employee_id', '-'))}</td></tr><tr><td>department</td><td>{e(c.get('department', '-'))}</td></tr>
<tr><td>job_title</td><td>{e(c.get('job_title', '-'))}</td></tr></table></div>
<div class=card><b>👥 Groups - where do they belong?</b> {e(', '.join(c.get('groups', [])) or '-')}<br>
<b>🎭 Realm roles:</b> {e(', '.join(r['realm']) or '-')}<br><b>🎭 Client roles ({CLIENT_ID}):</b> {e(', '.join(r['client']) or '-')}</div>
<div class=card><b>🔐 Access decisions (made from the token, not from the browser)</b><table>{rows}</table>
<form method=post action=/ask><input name=q size=50 placeholder="Ask NexaBank AI something..." required> <button>Ask</button></form></div>
<div class=card><b>⏱️ Session & token</b><table>
<tr><td>sid (Keycloak session)</td><td><code>{e(c.get('sid', '-'))}</code></td></tr>
<tr><td>auth_time (when you typed your password)</td><td>{ts('auth_time')}</td></tr>
<tr><td>iat (token issued)</td><td>{ts('iat')}</td></tr>
<tr><td>exp (token expires)</td><td>{ts('exp')} &nbsp;({int(c['exp'] - time.time())}s left)</td></tr></table></div>
<a class=btn href=/recheck>Re-check with Keycloak (live)</a> <a class=btn href=/forge>Try to forge an admin token</a>
<a class=btn href=/login>Refresh identity (login again)</a> <a class=btn href=/logout>Logout</a>
<details class=card><summary>Raw decoded token (JWT payload)</summary><pre>{e(payload)}</pre>
<b>Raw JWT</b> = header.payload.signature (never paste real tokens into websites):<pre>{e(token)}</pre></details>""")


@app.route("/ask", methods=["POST"])
def ask():
    _, c, err = current()
    if not c:
        return redirect("/me")
    allowed = "ai_user" in roles(c)["realm"]
    # The audit line names a VERIFIED human - this is what makes AI usage accountable.
    print(f"AUDIT {time.strftime('%H:%M:%S')} user={c['preferred_username']} sub={c['sub']} "
          f"allowed={allowed} prompt={request.form['q']!r}", flush=True)
    if not allowed:
        return page("403 Forbidden", "<div class='card bad'>❌ You need realm role <code>ai_user</code> to use the AI Assistant.</div>"
                    "<a class=btn href=/me>Back</a>"), 403
    return page("AI answer", f"<div class=card><b>You asked:</b> {e(request.form['q'])}<br><b>NexaBank AI (demo):</b> "
                f"Here is where a real model would answer. This request is logged against "
                f"<code>{e(c['preferred_username'])}</code> / <code>{e(c['sub'])}</code>.</div><a class=btn href=/me>Back</a>")


@app.route("/recheck")
def recheck():
    """Local verification only proves the token WAS valid. Ask Keycloak if the session is still alive NOW."""
    token, _, _ = current()
    if not token:
        return redirect("/")
    req = urllib.request.Request(f"{OIDC}/userinfo", headers={"Authorization": f"Bearer {token}"})
    try:
        info = json.load(urllib.request.urlopen(req))
        return page("Keycloak says: still valid", f"<div class='card good'>✅ Session is alive.</div><pre>{e(json.dumps(info, indent=2))}</pre><a class=btn href=/me>Back</a>")
    except urllib.error.HTTPError as ex:
        return page("Keycloak says: REJECTED", f"<div class='card bad'>❌ HTTP {ex.code} - Keycloak no longer accepts this token "
                    f"(session ended or user disabled), even though its signature is still valid.</div>"
                    f"<pre>{e(ex.headers.get('WWW-Authenticate', ''))}</pre><a class=btn href=/logout>Logout</a>")


@app.route("/forge")
def forge():
    """Edit the token payload to add 'admin', keep the original signature, and see if verification catches it."""
    token, c, _ = current()
    if not c:
        return redirect("/me")
    header, payload, sig = token.split(".")
    c.setdefault("realm_access", {}).setdefault("roles", []).append("admin")
    forged_payload = base64.urlsafe_b64encode(json.dumps(c).encode()).rstrip(b"=").decode()
    try:
        verify(f"{header}.{forged_payload}.{sig}")
        result = "<div class='card bad'>Forged token ACCEPTED - this should never happen!</div>"
    except jwt.PyJWTError as ex:
        result = f"<div class='card good'>🛡️ Forged token REJECTED: <b>{e(type(ex).__name__)}: {e(ex)}</b></div>"
    return page("Forgery attempt", f"""<div class=card>We took your real token, added <code>"admin"</code> to
<code>realm_access.roles</code>, and kept Keycloak's original signature.</div>{result}
<div class=card>The signature covers every byte of the payload. Only Keycloak's private key can produce a valid one.</div>
<a class=btn href=/me>Back</a>""")


@app.route("/logout")
def logout():
    t = TOKENS.pop(session.pop("k", None), None)
    if not t:
        return redirect("/")
    q = urllib.parse.urlencode({"id_token_hint": t["id_token"], "post_logout_redirect_uri": f"{APP_URL}/"})
    return redirect(f"{OIDC}/logout?{q}")  # ends the Keycloak SSO session too, not just the app's


if __name__ == "__main__":
    if not CLIENT_SECRET:
        print("WARNING: CLIENT_SECRET not set - login will fail at the token exchange step.")
    app.run(port=5000, debug=False)
