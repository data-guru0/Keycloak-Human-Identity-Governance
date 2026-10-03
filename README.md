# NexaBank AI Assistant — Keycloak Crash Course for Human Identity Governance


> **Keycloak is IAM (identity and access management), not a full IGA (identity governance and administration) platform.** It authenticates people and stores their groups, roles and attributes. Governance *processes* such as access reviews, approvals and HR-driven JML are what IGA tools add on top.


## Before class (10 min, once)

You need Docker Desktop and Python 3.10 or newer.

**1. Start Keycloak.** This guide uses port **8180** because 8080 is often already taken. Keep the port the same inside and outside the container (the Identity Provider demo depends on it).

```powershell
docker run -d --name keycloak -p 8180:8180 -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak:26.4 start-dev --http-port=8180
```

Open http://localhost:8180 and log in as `admin` / `admin`.
- The next day, run `docker start keycloak`. Your data is kept until you `docker rm` the container.
- To get a clean slate for the next class: `docker rm -f keycloak`, then run the command above again.

**2. Install the app's libraries.**

```powershell
cd app
pip install -r requirements.txt
```

**3. Start the app (do this during Stage 7).** You need the client secret, which you copy in Stage 7:

```powershell
$env:CLIENT_SECRET = "<paste from Keycloak > Clients > nexabank-ai-assistant > Credentials>"
python app.py
```

The app runs at http://localhost:5000. Stage 1 also works without Keycloak: open http://localhost:5000/no-keycloak.

**Classroom tip:** use one normal browser window for the **Admin Console** and one **private/incognito window** for the **app**. They keep separate cookies, so logging in as Rahul doesn't log you out of the admin console.

Demo credentials used in the guide: every user starts with the temporary password `Welcome@NexaBank1` and sets their own password at first login.
