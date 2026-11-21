# Wiki.js for NS8

Wiki.js 3.5.0 runs with PostgreSQL 17 in a rootless Podman pod. NS8 Traefik publishes the site over HTTPS.

Install a module image with `add-module ghcr.io/geniusdynamics/wikijs:<tag> 1`. Set the hostname and TLS in NS8 Settings, then complete Wiki.js setup in your browser and create a local administrator.

Wiki.js administration exposes its LDAP and OpenID Connect strategies. Automated NS8 directory discovery and OIDC registration are pending. Keep an independent local administrator when trying an external provider.

NS8 backup includes a logical PostgreSQL dump, protected database settings, and the content and repository volumes. [Wiki.js installation](https://docs.js.wiki/setup/installation)
