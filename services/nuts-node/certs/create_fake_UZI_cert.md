# Fake UZI Cert And VC

This repo already contains the generated certificate files in this folder:

- `mach2.disyepd.com.pem`
- `mach2.disyepd.com-chain.pem`
- `mach2.disyepd.com.key`

The DID currently used by the local/server stack is:

`did:web:mach2.disyepd.com:nuts-oauth2:iam:e21b9338-1f61-4a6b-9e28-866871d7c8a0`

## Create The VC On Windows PowerShell

Run this from the repo root:

```powershell
$certs = (Resolve-Path 'services/nuts-node/certs').Path
docker run --rm `
  -v "${certs}:/certs" `
  nutsfoundation/go-didx509-toolkit:1.1.0 `
  vc `
  /certs/mach2.disyepd.com-chain.pem `
  /certs/mach2.disyepd.com.key `
  "CN=Fake UZI Root CA" `
  "did:web:mach2.disyepd.com:nuts-oauth2:iam:e21b9338-1f61-4a6b-9e28-866871d7c8a0"
```

## Create The VC From Git Bash

Run this from the repo root:

```bash
CERTS_DIR="$(pwd -W)/services/nuts-node/certs"
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "${CERTS_DIR}:/certs" \
  nutsfoundation/go-didx509-toolkit:1.1.0 \
  vc \
  /certs/mach2.disyepd.com-chain.pem \
  /certs/mach2.disyepd.com.key \
  "CN=Fake UZI Root CA" \
  "did:web:mach2.disyepd.com:nuts-oauth2:iam:e21b9338-1f61-4a6b-9e28-866871d7c8a0"
```

## Why Git Bash Failed Before

If `CERTS_DIR` points to `/home/...` or another Git Bash path, Docker Desktop tries to mount a translated Windows path such as `C:\Program Files\Git\home\...`, which is not your repo and often fails with access errors.

Use:

- `pwd -W` to produce a Windows path
- `MSYS_NO_PATHCONV=1` to stop Git Bash from rewriting the bind mount argument

## Optional: Generate New Fake Cert Files

If you need to re-issue the fake certs instead of reusing the files already in this folder:

```bash
docker run --rm \
  -v "$(pwd -W)/services/nuts-node/certs:/work" \
  -w /work \
  alpine:3.19 \
  sh -lc '
    apk add --no-cache bash openssl git
    git clone --depth 1 https://github.com/nuts-foundation/go-didx509-toolkit.git /tmp/toolkit
    cd /tmp/toolkit/test_ca
    bash ./issue-cert.sh mach2.disyepd.com "Local Dev Org" "Locality" 00000000000 00000000 00700700
    cp -v /tmp/toolkit/test_ca/out/* /work
  '
```
