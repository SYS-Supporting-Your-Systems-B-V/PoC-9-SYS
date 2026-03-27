# Mock Notification Receiver

This service is a barebones receiver-side mock for local end-to-end testing of the BgZ sender flow.

Responsibilities:

- expose a receiver FHIR base with `GET /fhir/metadata`
- accept notification `Task` resources on `POST /fhir/Task`
- store received tasks in memory for inspection
- expose debug endpoints for manual Postman/curl testing

It is intentionally not a real receiver implementation:

- receiver-side auth is limited to bearer-token introspection plus `organization_ura` matching against `Task.requester.onBehalfOf.identifier.value`
- no signature or credential verification
- no FHIR profile validation
- no receiver-side workflow processing

Useful endpoints:

- `GET /health`
- `GET /fhir/metadata`
- `POST /fhir/Task`
- `GET /fhir/Task`
- `GET /fhir/Task/{id}`
- `GET /debug/tasks/latest`
- `GET /debug/tasks/latest-summary`
- `DELETE /debug/tasks`

Default public base:

- `https://mach2.disyepd.com/receiver-mock/fhir`

This path is meant for local self-tests where `iti-90` should discover a `Twiin-TA-notification` endpoint and successfully deliver a notification task without hitting the protected sender gateway route.

Current notification authorization behavior:

- `POST /fhir/Task` requires `Authorization: Bearer ...` by default
- the bearer token is introspected via the local Nuts node (`/internal/auth/v2/accesstoken/introspect`)
- the introspection result must contain `organization_ura`
- the token `organization_ura` must match `Task.requester.onBehalfOf.identifier.value`
- the token must include the configured receiver scope (default `eOverdracht-receiver`)
