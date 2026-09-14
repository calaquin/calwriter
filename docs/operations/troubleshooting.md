# Troubleshooting Guide

Common issues and diagnostic procedures for CalWriter.

---

## 1. Login Redirect Loop (Session Cookie Discarded)

- **Symptom**: You enter valid credentials, but after submitting, the browser bounces back to `/login` immediately without error.
- **Cause**: `SESSION_COOKIE_SECURE=true` is set while accessing over plain HTTP (`http://localhost:5000` or `http://localhost:5173`). Modern browsers discard `Secure` cookies over non-HTTPS connections.
- **Fix**:
  Ensure `.env` contains:
  ```bash
  SESSION_COOKIE_SECURE=false
  ```
  Then restart the app container:
  ```bash
  ./cw restart app
  ```

---

## 2. Port Conflicts (5000, 5432, 5173, 8080)

- **Symptom**: `docker compose up` fails with `address already in use`.
- **Diagnostic**: Check what process is occupying the conflicting port:
  ```bash
  sudo lsof -i :5000
  sudo lsof -i :5173
  sudo lsof -i :8080
  ```
- **Fix**: Stop the external host process or modify the port mapping in `docker-compose.override.yml`.

---

## 3. Database Connection Failure

- **Symptom**: `app` logs show `psycopg2.OperationalError: could not connect to server: Connection refused`.
- **Diagnostic**: Run `./cw doctor` or `./cw status`. Check PostgreSQL logs:
  ```bash
  ./cw logs db
  ```
- **Fix**: Verify `POSTGRES_PASSWORD` in `.env` matches the database container credentials.

---

## 4. Frontend Hot Reload Not Triggering

- **Symptom**: Editing files in `frontend/src/` does not update the browser at `http://localhost:5173`.
- **Fix**:
  Restart the frontend container:
  ```bash
  ./cw restart frontend
  ```
  Or run the frontend locally on the host:
  ```bash
  cd frontend && npm install && npm run dev
  ```

