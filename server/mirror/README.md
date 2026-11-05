# Website mirror receiver

The release workflow (`.github/workflows/release.yml`) uploads each tagged release to
`https://ai.z5a.com/owlpath-release-upload/<tag>/<file>` with a short-lived GitHub Actions OIDC token
(`scripts/publish-mirror.py`). `publisher.py` accepts it only when the token was issued for this public
repository (name and numeric ID), the `release.yml` workflow and a `push` of that tag. It checks every file
against `SHA256SUMS`, refuses to roll back, then atomically publishes:

- `/clients/owlpath/releases/vX.Y.Z/` with the four desktop packages, the source archive and `SHA256SUMS`
- `/clients/owlpath/latest.json` in the GitHub release API shape the desktop updater reads
- `/clients/owlpath/index.html`, a download page

No repository token, SSH key or password is stored on the server or in GitHub.

## One-time deployment (on the web server, as root)

```sh
install -d -m 755 /opt/owlpath-mirror /opt/sspanel/public/clients/owlpath
install -d -m 700 /opt/sspanel/storage/owlpath-release-incoming
install -m 644 publisher.py /opt/owlpath-mirror/publisher.py
install -m 644 owlpath-mirror.service /etc/systemd/system/owlpath-mirror.service
python3 -c "import cryptography"   # the receiver needs python3-cryptography
systemctl daemon-reload && systemctl enable --now owlpath-mirror
```

Add a reverse-proxy rule next to the existing release receiver, for example for nginx:

```nginx
location /owlpath-release-upload/ {
    client_max_body_size 17m;
    proxy_pass http://127.0.0.1:17013;
    proxy_request_buffering off;
}
```

`/clients/owlpath/` must be served as static files from `/opt/sspanel/public/clients/owlpath`.

Check: `curl -s -o /dev/null -w '%{http_code}\n' -X POST https://ai.z5a.com/owlpath-release-upload/v0.0.0/commit`
should print `403` (identity rejected), not `404` or `502`.

If the mirror was down during a release, re-run the workflow's `release` job for that tag; uploads resume and the
commit is idempotent.

Tests: `python3 server/mirror/test_publisher.py` (needs `cryptography`).
