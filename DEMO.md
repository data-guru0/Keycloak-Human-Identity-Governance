# NexaBank AI Assistant — Human Identity Governance with Keycloak

> Setup is in [README.md](README.md). Keep the **Admin Console** in a normal window and the **app** in a private/incognito window.

---

## Stage 1 — The problem: an app without real identity

**Theory.** An application needs to know *who* is calling and *what they may do*. If it takes that from the request itself (a form field, a header, a URL parameter), the caller can just claim whatever they want. Identity has to be **proven** (authentication) and **vouched for** by a party the app trusts (a signed token).

**What to do.** Start the app (`python app.py`; no secret is needed for this stage). Open http://localhost:5000 and click **Open the app WITHOUT Keycloak**.


---

## Stage 2 — Realm: the identity boundary, with audit on from day one

**Theory.** A **realm** is a self-contained identity world with its own users, groups, roles, applications, login policies and signing keys. Tokens from one realm are worthless in another. The `master` realm is only for administering Keycloak; never put business users there.

**What to do in the UI.**
1. Log in at http://localhost:8180 as `admin`/`admin`. Point out that you are in the **master** realm.
2. **Manage realms → Create realm.**  Set **Realm name** `nexabank` and click **Create**.
3. **Realm settings → General:** set **Display name** `NexaBank` and click **Save**.
4. **Realm settings → Events tab → User events settings:** turn **Save events** ON and click **Save**.
5. **Events tab → Admin events settings:** turn **Save events** ON and **Include representation** ON, then click **Save**.
6. (Show only) **Realm settings → Login tab:** **User registration** is OFF. Nobody can create their own account.


---

## Stage 3 — Attributes: define the identity schema

**Theory.** **Attributes** describe a person: employee ID, department, job title. In governance, attributes drive decisions ("everyone in Model Risk is a reviewer") and must be **trustworthy**. If users could edit their own department, they could change their own access.

**What to do in the UI.** Go to **Realm settings → User profile tab → Create attribute**, twice:

| Attribute [Name] | Display name | Who can edit? | Who can view? |
|---|---|---|---|
| `employee_id` | Employee ID | **Admin only** (untick User) | Admin + User |
| `department` | Department | **Admin only** | Admin + User |

AI Engineering and IT Security are the departments

Leave **Required field** OFF and click **Create** each time.

---

## Stage 4 — Users, credentials and required actions

**Theory.**
- A **User** is the digital identity of one human.
- A **Credential** is how they prove it (password, OTP, passkey).
- A **Required action** is something the user *must* do at their next login, for example change a temporary password.

- Onboarding a new person is the **Joiner** step of the identity lifecycle.

**What to do in the UI.**
1. *


*
2. **Users → Create new user** for Rahul:
   - **Email verified** ON
   - **Username** `rahul`, **Email** `rahul@nexabank.example`
   - **First name** Rahul, **Last name** Sharma
   - **Employee ID** `NB-1001`, **Department** `AI Engineering`
   - Click **Create**.
3. On Rahul's page: **Credentials tab → Set password.** Enter `Welcome@NexaBank1` with **Temporary** ON, then **Save**.
4. Repeat for **sudhanshu** (Sudhanshu Gusain, `NB-0001`, `IT Security`), same temporary password.
5. For **sudhanshu** only: on the **Details tab**, set **Required user actions** to **Configure OTP** and click **Save**. 


---

## Stage 5 — Groups and nested groups

**Theory.** A **Group** says *where a person belongs* (org unit, team, function). Groups can be nested, and **child groups inherit their parents' roles**. You manage access for 1,000 people by managing 10 groups.

**What to do in the UI.**
1. **Groups → Create group:** `Employees`.
2. Open **Employees → Child groups tab → Create group:** `AI-Team`.
3. Back at the top level: **Create group** `Administrators`. It is deliberately *not* under Employees: privileged access lives in its own, tightly watched group.
4. Put people in groups via **Users → (user) → Groups tab → Join group** (tick the group, **Join**):

| User | Join |
|---|---|
| rahul | /Employees/AI-Team |
| sudhanshu | /Employees **and** /Administrators |


---

## Stage 6 — Realm roles, direct vs group-inherited assignments

**Theory.**
- A **Role** is an access designation: *what the person is allowed to be* (employee, ai_user, admin).
- **Realm roles** are realm-wide.
- Roles can be assigned **directly** to a user or **through a group**. Group-based is the governance-friendly default, because when someone leaves the group, the access goes with it.

**What to do in the UI.**
1. **Realm roles → Create role** three times: `employee`, `ai_user`, `admin`. Give each a one-line **Description**, e.g. *"May use the NexaBank AI Assistant"*.
2. Give roles to groups: **Groups → (group) → Role mapping tab → Assign role → Realm roles** (filter dropdown) → tick → **Assign**:

| Group | Realm role |
|---|---|
| Employees | employee |
| AI-Team | ai_user |
| Administrators | admin |

Rahul gets `employee` **inherited** from Employees plus `ai_user` from AI-Team. Sudhanshu is an admin but *not* in AI-Team, so he can't use the assistant: least privilege.

---

## Stage 7 — Client: register the NexaBank AI Assistant

**Theory.**
- A **Client** is an application that relies on Keycloak to log users in.
- **Client roles** are permissions that only mean something *inside that one app*.
- **Mappers** decide which identity facts (groups, attributes) are copied into the token the app receives.

**What to do in the UI.**
1. **Clients → Create client.**
   - **General settings:** Client type `OpenID Connect`, **Client ID** `nexabank-ai-assistant`, **Name** `NexaBank AI Assistant`. Click **Next**.
   - **Capability config:** **Client authentication** ON (a confidential app with a secret). **Standard flow** ✅. **Direct access grants** ☐ (the app must never handle passwords). Click **Next**.
   - **Login settings:**
     - **Root URL** `http://localhost:5000`
     - **Valid redirect URIs** `http://localhost:5000/callback`
     - **Valid post logout redirect URIs** `http://localhost:5000/*`
     - **Web origins** `http://localhost:5000`
     - Click **Save**.
2. **Credentials tab:** copy the **Client secret**. Start the app:
   ```powershell
   $env:CLIENT_SECRET = "<paste>"; python app.py
   ```
3. **Roles tab → Create role:** `manage_assistant`.
4. Give it to a group: **Groups → Administrators → Role mapping → Assign role**, switch the filter to **Client roles**, search `nexabank`, tick `manage_assistant` and click **Assign**.
5. Put groups and attributes into the token. Go to **Clients → nexabank-ai-assistant → Client scopes tab → `nexabank-ai-assistant-dedicated` → Configure a new mapper**:
   - **Group Membership:** Name `groups`, Token Claim Name `groups`, **Full group path** ON. Click **Save**.
   - Go back and choose **Add mapper → By configuration → User Attribute** twice. Each time: Name = User Attribute = Token Claim Name = `employee_id`, then `department`. Claim JSON type `String`. Click **Save**.


---

## Stage 8 — Authentication: Rahul logs in with OIDC

**Theory.** **Authentication** = proving identity. With **OpenID Connect (OIDC)** the app *never sees the password*:
1. The app sends the browser to Keycloak.
2. Keycloak checks the credential.
3. Keycloak sends back a one-time **code**.
4. The app exchanges the code (plus its client secret) for **tokens**, directly with Keycloak.

```
 Browser                   NexaBank AI app                Keycloak (realm nexabank)
   |-- click Login --------->|                                  |
   |<-- 302 to /auth --------|                                  |
   |-------------------- GET /auth?client_id&redirect_uri ----->|
   |<------------------- login page ----------------------------|
   |-------------------- rahul + password -------------------->|  checks hash, required actions
   |<------------------- 302 /callback?code=XYZ ----------------|  creates SSO SESSION
   |-- /callback?code=XYZ -->|                                  |
   |                         |-- POST /token (code + secret) -->|  back channel
   |                         |<-- access_token, id_token -------|  signed with realm private key
   |                         |  verify signature with PUBLIC key (jwks)
   |<-- "Hello, Rahul" ------|
```

**What to do.** In the private window, open http://localhost:5000 → **Login with Keycloak** → `rahul` / `Welcome@NexaBank1`.

**Students observe.**
1. The URL changes to `localhost:8180/realms/nexabank/...`: we are on **Keycloak's** page, not the app's.
2. Keycloak shows **"Update password"** (the required action from Stage 4). Set a new one, e.g. `Rahul@NexaBank2026`.
3. We land on the app: **"Hello, Rahul Sharma"** with his attributes, groups and roles, and **Ask the AI Assistant ✅ ALLOWED**, the other three ❌ DENIED.


---

## Stage 9 — The token: claims, and why it can't be forged

**Theory.** The **access token** is a **JWT**: three parts, `header.payload.signature`.
- The payload holds **claims** (facts about the user and the login).
- The signature is made with the realm's **private key**. Anyone can *read* a JWT, but only Keycloak can *produce* a valid one.

**What to do.** On Rahul's app page, open **Raw decoded token** and walk through the claims:

| Claim | Meaning | Governance angle |
|---|---|---|
| `iss` | Issuer: `http://localhost:8180/realms/nexabank` | Which realm vouches for this person |
| `sub` | Permanent user ID (UUID) | Audit key; doesn't change if the username changes |
| `azp` | *Authorized party*: the client the token was issued to | The app rejects tokens issued to other apps |
| `aud` | Audience (`account` here, a default) | Who the token is meant for |
| `exp` / `iat` | Expiry / issued-at (5 min lifetime) | Tokens are **short-lived snapshots** |
| `auth_time` | When the human actually authenticated | Force re-authentication for risky actions |
| `sid` | Keycloak session ID | Links the token to a session you can kill |
| `preferred_username`, `name`, `email` | Who | |
| `groups` | `["/Employees/AI-Team"]` (our mapper) | Where they belong |
| `realm_access.roles` | `employee`, `ai_user`, plus defaults | What they may do |
| `resource_access.<client>.roles` | Client roles | App-specific permissions |
| `employee_id`, `department` | Our attribute mappers | What describes them |

Note `offline_access`, `uma_authorization` and `default-roles-nexabank`: every user gets these from the realm's **default roles**. That's a good question for the class: *"Should every user get any role by default?"*

---

## Stage 10 — Sessions and events: the evidence trail

**Theory.**
- A **Session** is Keycloak's record that "Rahul is currently authenticated" (SSO). Tokens are issued *from* a session.
- **Events** are the audit log. **User events** record logins and failures. **Admin events** record who changed what.

**What to do in the UI.**
1. **Sessions** (left menu): Rahul's session shows IP, start time, last access and the client `nexabank-ai-assistant`.
2. **Users → rahul → Sessions tab:** the same session from the user's point of view.
3. **Events → User events:** `LOGIN`, `CODE_TO_TOKEN`, `UPDATE_PASSWORD` for rahul. Expand one to see IP, client and session ID.
4. **Events → Admin events:** `CREATE GROUP_MEMBERSHIP`, `CREATE REALM_ROLE_MAPPING`… Expand one and show **Representation**: the exact change, with who made it and when.

---
