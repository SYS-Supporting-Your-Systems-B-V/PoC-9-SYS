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
docker compose up
```

Main local endpoints:

- ITI-91 API docs: <http://localhost:8509/docs>
- ITI-90 API docs: <http://localhost:8000/docs>
- Directory FHIR: <http://localhost:8080/fhir>
- Update Client FHIR: <http://localhost:8081/fhir>
- Notified Pull FHIR: <http://localhost:8082/fhir>

## Configuration files

Before starting, verify:

1. `iti-91.conf`  
   ITI-91 runtime configuration mounted as `/src/app.conf`.
2. `.env`  
   Compose-level settings such as profiles (`COMPOSE_PROFILES`).
3. `../services/iti-90/.env.Docker`  
   ITI-90 runtime settings loaded by `iti-90-address-book-proxy` via `env_file`.
   The most important values are `MCSD_BASE` (upstream FHIR base) and `MCSD_SENDER_*`
   for BgZ notification sender identity.
4. `client.application.yaml`, `directory.application.yaml`, `notifiedpull-stu3.application.yaml`  
   HAPI server configuration files used by this compose stack.
5. `create-dbs.sql`  
   Postgres init script used on first database startup.

Template files:

- `iti-91.conf.example` -> copy to `iti-91.conf`
- `.env.example` -> copy to `.env`

## Optional Caddy profile

Enable Caddy in one of these ways:

```bash
# option 1: in .env
COMPOSE_PROFILES=caddy

# option 2: command line
docker compose --profile caddy up
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
