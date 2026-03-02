# PoC-9-SYS

This repository contains reference implementations for mCSD-based workflows in the
"Generieke Functies, lokalisatie en addressering" context, covering ITI-90,
ITI-91, and ITI-130 in one integrated PoC setup.

> [!CAUTION]
> This repository is a **reference implementation**. It is **NOT** intended for
> production use.

## What is in this repository

- `services/iti-91`: ITI-91 Request Care Services Update service
- `services/iti-130`: ITI-130 Care Services Feed publisher
- `services/iti-90`: ITI-90 address book proxy (PoC-focused)
- `poc9-start-stack`: Docker Compose stack to run the full PoC locally

## IHE transaction scope (all are in scope)

This repository is designed around these three IHE mCSD transactions:

- [ITI-90: Find Matching Care Services](https://profiles.ihe.net/ITI/mCSD/ITI-90.html)  
  Implemented in `services/iti-90` for query/search flows used by the sender.
- [ITI-91: Request Care Services Update](https://profiles.ihe.net/ITI/mCSD/ITI-91.html)  
  Implemented in `services/iti-91` for synchronization/update flows.
- [ITI-130: Care Services Feed](https://profiles.ihe.net/ITI/mCSD/ITI-130.html)  
  Implemented in `services/iti-130` for publishing source data into the directory model.

## PoC scope from PvA (Route PoC 9, sending party)

For PoC 8/9 Route 9, this repository focuses on the **sending party** role in an
MSZ-to-MSZ BgZ referral flow, using GF Adressering with TA Routering.

Core principles covered by this repository:

- Use representative real-life organizational data in the mCSD directory model.
- Find MSZ organizations, organizational units, and technical endpoints via the address book.
- Support endpoint discovery needed for BgZ routing (FHIR, notification, authentication).
- Compose the notification task targeted to a specific receiving organizational unit.
- Support end-to-end PoC demonstration with paired sender/receiver parties.

Technical specifications used for this PoC include the NL GF care services IG:
<https://nuts-foundation.github.io/nl-generic-functions-ig/care-services.html>

## Documentation map

- Repository + full-stack startup: this file
- Stack details and operations: [`poc9-start-stack/README.md`](poc9-start-stack/README.md)
- ITI-91 update client service details: [`services/iti-91/README.md`](services/iti-91/README.md)
- ITI-91 update client architecture/flow docs: [`services/iti-91/docs/README.md`](services/iti-91/docs/README.md)
- ITI-130 details: [`services/iti-130/README.md`](services/iti-130/README.md)
- ITI-90 details: [`services/iti-90/README.md`](services/iti-90/README.md)

## Start the full repository stack

From the repository root:

```bash
cd poc9-start-stack
docker compose up
```

After startup:

- ITI-91 API docs: <http://localhost:8509/docs>
- ITI-90 API docs: <http://localhost:8000/docs>
- Directory FHIR (without Caddy): <http://localhost:8080/fhir>
- Update Client FHIR: <http://localhost:8081/fhir>
- Notified Pull FHIR: <http://localhost:8082/fhir>
- Postgres: `localhost:5432`
- Redis: `localhost:16379`
- Caddy HTTPS endpoint: <https://localhost:443> (when profile `caddy` is enabled)

For full stack instructions (profiles, seeding, endpoints, operations), see
[`poc9-start-stack/README.md`](poc9-start-stack/README.md).

## Configuration checklist for a working full stack

Before `docker compose up`, check these files:

1. `poc9-start-stack/iti-91.conf`  
   Copy from `poc9-start-stack/iti-91.conf.example` and adjust ITI-91 runtime settings.
2. `poc9-start-stack/.env`  
   Copy from `poc9-start-stack/.env.example` if you want to enable optional profiles
   (for example `COMPOSE_PROFILES=caddy`).
3. `services/iti-90/.env.Docker`  
   Runtime settings for `iti-90-address-book-proxy` in the compose stack (loaded via
   `env_file`). Check `MCSD_BASE` and, for BgZ endpoints, `MCSD_SENDER_*` values.
4. `secrets/cloudflare_api_token` (only when using Caddy profile)  
   Required by the optional Caddy service.

## Disclaimer

This project and all associated code serve solely as documentation and
demonstration purposes to illustrate potential system communication patterns
and architectures.

This codebase:

- Is NOT intended for production use
- Does NOT represent a final specification
- Should NOT be considered feature-complete or secure
- May contain errors, omissions, or oversimplified implementations
- Has NOT been tested or hardened for real-world scenarios

The code examples are only meant to help understand concepts and demonstrate possibilities.

By using or referencing this code, you acknowledge that you do so at your own
risk and that the authors assume no liability for any consequences of its use.

## Contribution

As stated in the [Disclaimer](#disclaimer), this repository accepts contributions
that fit the documentation/reference-implementation goal.

Because maintainer time is limited, issues/PRs may be closed without a full
justification.

If you plan non-trivial changes, open an issue first to discuss scope and
fit before implementation work.

All commits should be signed using a GPG key.

## Licensing

- **Code**: MIT (see `LICENSE`), except where noted (for example `services/iti-91`).
- **Documentation**: CC BY-SA 4.0 (see `LICENSES/CC-BY-SA-4.0.txt`).
- **Third-party dependencies**: see `THIRD_PARTY_LICENSES.md` files per service.
