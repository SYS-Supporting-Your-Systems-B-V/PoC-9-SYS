# generate fake UZI certs via Docker (no local toolkit install)
$ CERTS_DIR="/home/yob/PoC-9-SYS/services/nuts-node/local-dev/test"
$ mkdir -p "$CERTS_DIR"

# copy the test_ca template from the image into your host folder and issue the certs there
$ docker run --rm \
  -v "$CERTS_DIR:/work" \
  -w /work \
  alpine:3.19 \
  sh -lc '
    apk add --no-cache bash openssl git
    git clone --depth 1 https://github.com/nuts-foundation/go-didx509-toolkit.git /tmp/toolkit
    cd /tmp/toolkit/test_ca
    bash ./issue-cert.sh mach2.disyepd.com "ZBC Demo Kliniek" "Locality" 00000000000 00000000 00700700
    cp -v /tmp/toolkit/test_ca/out/* /work
  '


# create x.509 credential which must be added to the DID
$ docker run --rm -v "$CERTS_DIR:/certs" nutsfoundation/go-didx509-toolkit:1.1.0 vc /certs/mach2.disyepd.com-chain.pem /certs/mach2.disyepd.com.key "CN=Fake UZI Root CA" did:web:localhost%3A8083:iam:3f91f049-b385-4351-bba5-e192bd1b3ab6
