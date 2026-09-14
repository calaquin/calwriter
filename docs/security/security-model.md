# Security Model

CalWriter's security posture is designed for safe local and private-network development and multi-user authoring.

---

## 1. Authentication & Password Security

- User passwords are never stored in plaintext.
- Password hashes use Werkzeug's secure hashing implementation (`scrypt` / `pbkdf2:sha256`).
- Admin accounts are created strictly via CLI (`./cw user:create <username> --admin`) to prevent unauthorized self-registration.

---

## 2. Session Cookies & Transport Security

- Flask session cookies use `HttpOnly` and `SameSite=Lax` flags to mitigate cross-site scripting (XSS) and cross-site request forgery (CSRF) vulnerabilities.
- `SESSION_COOKIE_SECURE` must be set to `true` when deployed behind HTTPS / TLS termination reverse proxies.

---

## 3. Network Exposure & Local-Only Dev Utilities

- **Loopback Binding**: By default, Docker Compose exposes service ports on the local machine loopback interface (`127.0.0.1` / `localhost`).
- **Adminer Autologin**:
  - The Adminer container (`:8080`) has hardcoded auto-authentication configured in `docker-compose.override.yml` for local developer convenience.
  - **CRITICAL**: Adminer is strictly prohibited in production and shared environments. The `docker-compose.override.yml` file is excluded from production image builds.

---

## 4. Agent Execution Boundaries

In accordance with **Workspace Bootstrap Standard v1.0 (WBS 1.0)**, all AI coding assistants operating on this codebase are strictly confined to the local machine:
- No remote code pushing (`git push` is prohibited).
- No remote deployments, SSH sessions, or publication of container images.
- All operations are validated locally prior to commit.

