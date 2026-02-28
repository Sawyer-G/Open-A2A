# Self-Hosted Solid Pod Guide

> Aligns with Open-A2A data sovereignty: preferences stored on your own server, no third-party platform dependency.

## 1. Why Self-Host

| Approach | Data Location | Aligns with Design |
|----------|---------------|--------------------|
| **profile.json** | Local file | ✅ Yes |
| **Self-hosted Solid** | Your own server | ✅ Yes |
| Third-party Pod provider | Their server | ❌ No |

Self-hosted Solid preserves data sovereignty while offering standard protocol and fine-grained access control.

## 2. Quick Deploy (Docker)

```bash
docker compose -f docker-compose.solid.yml up -d

# Visit https://localhost:8443 to register
# Self-signed cert will show "insecure"—proceed for local dev
```

**Multi-user**: For subdomains (e.g. `alice.localhost`), add to `/etc/hosts`:
```
127.0.0.1 alice.localhost
```

## 3. Configure Open-A2A

Set in `.env` or environment:

```bash
SOLID_IDP=https://localhost:8443/
SOLID_POD_ENDPOINT=https://localhost:8443/your-username/
SOLID_USERNAME=your-username
SOLID_PASSWORD=your-password
```

## 4. Upload Preferences to Pod

```bash
make install-solid   # or pip install open-a2a[solid]
python example/upload_profile_to_solid.py
```

## 5. Run Consumer

With `SOLID_POD_ENDPOINT` set, Consumer reads preferences from your self-hosted Pod:

```bash
make run-consumer
```

## 6. Production

- Set `SOLID_SERVER_URI` to your domain (e.g. `https://solid.yourdomain.com`)
- Mount real certificates (e.g. Let's Encrypt)
- See [docker-solid-server examples](https://github.com/angelo-v/docker-solid-server/tree/main/examples)
