# ITI-91 mCSD Update Client

This app is the mCSD (Mobile Care Service Discovery) Update Client and is part of
the "Generieke Functies, lokalisatie en addressering" project of the Ministry of
Health, Welfare and Sport of the Dutch government.

The purpose of this application is to perform updates on
[mCSD supported resources](https://profiles.ihe.net/ITI/mCSD/index.html). The
update uses HTTP as a basis for CRUD operations and works independently of the
FHIR store type.

> [!CAUTION]
> This service is a **reference implementation** for
> [ITI-91: Request Care Services Update](https://profiles.ihe.net/ITI/mCSD/ITI-91.html).

## Reference implementation

This codebase serves as an example of how the mCSD ITI-91 update mechanism can
be implemented. It is **NOT** intended for production use.

### Purpose

- Demonstrate mCSD system communication patterns
- Support documentation and proof-of-concept development
- Enable basic interoperability testing

### Use cases

Use this to:

- Understand how mCSD updates work in practice
- Explore Update Client and Data Source interactions
- Prototype or test mCSD-compliant behaviors

## Service docs

- Architecture and behavior details: [`docs/README.md`](docs/README.md)
- Full PoC stack startup and operations: [`../../poc9-start-stack/README.md`](../../poc9-start-stack/README.md)
- Repository-level setup/contribution/license context: [`../../README.md`](../../README.md)

## Setup context

To test the update mechanism, you need at least two FHIR stores:

- one [Update Client](https://profiles.ihe.net/ITI/mCSD/4.0.0-comment/volume-1.html#146113-update-client)
- at least one [Data Source](https://profiles.ihe.net/ITI/mCSD/4.0.0-comment/volume-1.html#146114-data-source)

You can use a [HAPI JPA server](https://hapifhir.io/hapi-fhir/) or any other
FHIR store, as long as mCSD requirements are supported.

In this repository, these dependencies are provided by the Compose stack in
`poc9-start-stack`.

The ITI-91 runtime config file is `poc9-start-stack/iti-91.conf`
(copy `poc9-start-stack/iti-91.conf.example` to get started).

## Docker container builds

There are two ways to build a Docker container from this service.

Default mode:

```bash
cd services/iti-91
make container-build
```

This builds a container that runs migrations against the database configured in
`poc9-start-stack/iti-91.conf` (mounted as `/src/app.conf`).

Standalone mode:

```bash
cd services/iti-91
make container-build-sa
```

Standalone mode does not generate migrations automatically. You must explicitly
mount an `iti-91.conf` file to `/src/app.conf`.

Both images differ only in init script behavior. The default mode usually mounts
its own local source directory into `/src`.

## URL resolving of references

When encountering absolute URLs in references, they are resolved only when the
URL has the same origin. Otherwise an exception is raised.

## Required interactions for FHIR directories

The Update Client can verify whether a FHIR directory supports required
interactions by checking its CapabilityStatement. This check is automatic when
enabled in configuration.

A general mCSD capability statement can be found at:
<https://profiles.ihe.net/ITI/mCSD/CapabilityStatement-IHE.mCSD.Directory.html>

This Update Client expects FHIR R4 servers to support the following resources
with these interactions:

| Resource | Interactions required |
| --- | --- |
| Organization | read, search-type, history-type |
| Practitioner | read, search-type, history-type |
| PractitionerRole | read, search-type, history-type |
| Location | read, search-type, history-type |
| Endpoint | read, search-type, history-type |
| HealthcareService | read, search-type, history-type |
| OrganizationAffiliation | read, search-type, history-type |

Additionally, the directory must operate as an FHIR R4 REST server without
authentication for this reference setup.

## Disclaimer

This service and all associated code serve solely as documentation and
demonstration purposes to illustrate potential system communication patterns and
architectures.

It is not intended for production use and may contain errors, omissions, or
oversimplified implementations.

## Licensing

- **Service code**: EUPL-1.2 (see `LICENSE.md` in this folder).
- **Repository docs/license context**: see [`../../README.md`](../../README.md).

