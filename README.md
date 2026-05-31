# JAGUAR TECHNOLOGIES

JAGUAR TECHNOLOGIES is a GPL-3.0 ISP Wi-Fi billing, security, payment, RADIUS, and satellite-linking platform. It combines a FastAPI backend with an installable orange-branded web/PWA frontend and FreeRADIUS integration points so an ISP can run one admin-controlled console for customer access, billing, and security operations.

> Production note: this repository provides source code and deployment templates. Before connecting live subscribers, replace every default secret, configure TLS, connect a managed database, and complete a security review for your local laws, payment providers, and ISP network.

## Core capabilities

- **Admin-only control plane** for users, plans, subscribers, RADIUS secrets, satellite linking, and security functions.
- **FreeRADIUS compatible authorization API** for PAP/CHAP policy flows through `rlm_rest`.
- **Global payment webhook pattern** for providers such as Stripe, PayPal, Flutterwave, M-Pesa, Airtel Money, and bank aggregators.
- **Security functions** including JWT auth, optional TOTP MFA for staff, role-based access control, signed payment webhooks, RADIUS shared-secret checks, audit/security events, and secure browser headers.
- **Satellite integration link point** for satellite terminal IDs and provider APIs.
- **Installable apps** through PWA support for desktop and mobile browsers, with a path to package the same frontend for Google Play and Apple App Store using Capacitor or a similar wrapper.

## Project structure

```text
backend/app/              FastAPI application, database models, schemas, and security helpers
frontend/                 Orange JAGUAR TECHNOLOGIES PWA frontend
deploy/freeradius/        FreeRADIUS rlm_rest integration template
tests/                    API and RADIUS authorization checks
Dockerfile                Container image for the API + frontend
docker-compose.yml        Local/VM deployment starter
app.yaml                  Google App Engine starter
cloudbuild.yaml           Google Cloud Run deployment pipeline
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e '.[test]'
uvicorn backend.app.main:app --reload
```

Open <http://localhost:8000> and sign in with the bootstrap account:

- Email: `admin@jaguar.local`
- Password: `ChangeMeNow!2026`

Immediately change these values in production using environment variables.

## Docker deployment

```bash
docker compose up --build
```

Set these environment variables with production values:

- `DATABASE_URL`
- `JWT_SECRET`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `FREERADIUS_SHARED_SECRET`
- `PAYMENT_WEBHOOK_SECRET`
- `SATELLITE_API_KEY`

## FreeRADIUS integration

Use `deploy/freeradius/jaguar-rlm-rest.conf` as the starter for `mods-enabled/rest`. Point `connect_uri` at your deployed API and set `X-Radius-Secret` to the same value as `FREERADIUS_SHARED_SECRET`.

The API endpoint is:

```http
POST /api/radius/authorize
X-Radius-Secret: <secret>
Content-Type: application/json

{
  "username": "subscriber-radius-user",
  "password": "subscriber-radius-password",
  "nas_ip_address": "10.0.0.1"
}
```

A successful response includes `rate_limit` and `radius_group`, which can be mapped to Mikrotik, Cisco, Cambium, Ubiquiti, or other NAS policies.

## Global payment integration

Payment providers should call `POST /api/payments/webhook` after settlement. The current source uses an HMAC signature over:

```text
provider_reference:amount:currency
```

using `PAYMENT_WEBHOOK_SECRET`. Add provider-specific adapters for Stripe, PayPal, Flutterwave, M-Pesa, Airtel Money, or bank channels by validating their native signatures, then normalizing into the included `PaymentIn` schema.

## Satellite system linking

Admins can link a customer account to a satellite terminal with `POST /api/satellite/link`. The endpoint is intentionally provider-neutral and can be connected to Starlink enterprise APIs, VSAT OSS/BSS systems, NMS platforms, or proprietary satellite gateways through a small adapter that translates provider terminal IDs and service state.

## Google Cloud deployment

This repository includes `cloudbuild.yaml` for Google Cloud Run and `app.yaml` for App Engine-style deployments. Store secrets in Secret Manager, bind them to runtime environment variables, and place the service behind HTTPS before connecting RADIUS, payments, or satellite systems.

```bash
gcloud builds submit --config cloudbuild.yaml --substitutions _REGION=us-central1
```

## Mobile, desktop, Google Play, and App Store path

The included frontend is a PWA and can be installed from supported desktop and mobile browsers. For stores:

1. Keep `frontend/manifest.webmanifest` and `frontend/service-worker.js` enabled.
2. Wrap the deployed web app with Capacitor, Tauri, or another audited native shell.
3. Configure Android package signing and Apple bundle identifiers.
4. Submit through Google Play Console and Apple App Store Connect after legal, privacy, and payment compliance review.

## Tests

```bash
pytest
ruff check .
```
