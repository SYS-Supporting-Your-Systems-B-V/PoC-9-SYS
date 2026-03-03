# PoC 9 Start Stack

This folder contains the Docker Compose setup used to run the full PoC stack
locally.

## What this stack starts

- `iti-91-mcsd-update-client`: ITI-91 update client API
- `iti-130-publisher`: ITI-130 publisher helper
- `iti-90-address-book-proxy`: ITI-90 proxy API
- `hapi-directory`: mock directory FHIR server
- `hapi-update-client`: update-client-side FHIR server
- `hapi-notifiedpull-stu3`: notified-pull FHIR server
- Healthcheck helper containers
- Supporting services: `postgres`, `redis`
- Optional profile: `caddy`

## Start

From the repository root:

```bash
cd poc9-start-stack
docker compose up -d 
```

Main local endpoints:

- ITI-91 API docs: <http://localhost:8509/docs>
- ITI-90 API docs: <http://localhost:8000/docs>
- Directory FHIR: <http://localhost:8080/fhir>
- Update Client FHIR: <http://localhost:8081/fhir>
- Notified Pull FHIR: <http://localhost:8082/fhir>

## Config map

Use this table to identify what must be configured for your own setup.

| File / Variable | Used by service(s) | Required | Purpose |
| --- | --- | --- | --- |
| `iti-91.conf` | `iti-91-mcsd-update-client` | Yes | Main ITI-91 runtime config (mounted to `/src/app.conf`) |
| `iti-91.conf:[mcsd]update_client_url` | `iti-91-mcsd-update-client` | Yes | Target FHIR base where ITI-91 writes synchronized resources |
| `iti-91.conf:[client_directory]directories_provider_urls` | `iti-91-mcsd-update-client` | Yes (when using LRZa discovery) | One or more directory-registry/LRZa endpoints |
| `.env` | `docker compose` | Usually | Local compose toggles (for example `COMPOSE_PROFILES`) |
| `.env:COMPOSE_PROFILES` | `docker compose` | No | Optional profile toggles such as `caddy` |
| `../services/iti-90/.env.Docker` | `iti-90-address-book-proxy` | Yes | ITI-90 runtime settings loaded via `env_file` |
| `../services/iti-90/.env.Docker:MCSD_BASE` | `iti-90-address-book-proxy` | Yes | Upstream mCSD/FHIR base URL for ITI-90 |
| `../services/iti-90/.env.Docker:MCSD_SENDER_*` | `iti-90-address-book-proxy` | Required for BgZ notify flow | Sender identity used in PoC notification flows |
| `client.application.yaml` | `hapi-update-client` | Yes | HAPI config for update-client-side FHIR server |
| `directory.application.yaml` | `hapi-directory` | Yes | HAPI config for source directory FHIR server |
| `notifiedpull-stu3.application.yaml` | `hapi-notifiedpull-stu3` | Yes | HAPI config for notified-pull FHIR server |
| `create-dbs.sql` | `postgres` | Yes | Database initialization script (first startup) |
| `../secrets/cloudflare_api_token` | `caddy` | Only if `caddy` profile enabled | Cloudflare API token used by Caddy |

Starter templates:

- `iti-91.conf.example` -> `iti-91.conf`
- `.env.example` -> `.env`

## Optional Caddy profile

Enable Caddy in one of these ways:

```bash
# option 1: in .env
COMPOSE_PROFILES=caddy

# option 2: command line
docker compose --profile caddy up -d
```

The Caddy profile requires `../secrets/cloudflare_api_token`.

Without Caddy, you can still access the directory directly at
`http://localhost:8080/fhir`.


## Stop and clean up

```bash
docker compose down
```

To also remove named volumes created by this stack:

```bash
docker compose down -v
```
