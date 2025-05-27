# Docker Registry & Management Utilities

A **self‑hosted Docker Registry** (✅ *registry* folder) bundled with handy **management scripts** (✅ *manage* & *manager* folders) so you can push, browse, and prune images from your own private registry running on‑prem or in the cloud.

> **Why?** Local registries remove the network hop to Docker Hub, keep proprietary images private, and are a perfect drop‑in while you experiment before jumping to providers like AWS ECR.

---

## 📂 Repository layout

| Path        | Purpose                                                                   |
| ----------- | ------------------------------------------------------------------------- |
| `registry/` | Docker Compose stack: registry + optional UI + reverse‑proxy.             |
| `manage/`   | Python/Go helper scripts (list images, delete stale tags, report usage…). |
| `manager/`  | Misc. utilities / PoC code that may graduate into *manage/*.              |

*(Names are self‑explanatory; see the individual READMEs or **`--help`** flags for details.)*

---

## 🚀 Quick start

```bash
# 1. Clone
$ git clone https://github.com/KiranM0008/Docker-registry-and-manage.git
$ cd Docker-registry-and-manage

# 2. Launch the registry stack (defaults to port 5000)
$ cd registry
$ docker compose up -d  # 🎉 registry is now on http://localhost:5000

# 3. Push your first image
$ docker pull alpine:3.19
$ docker tag alpine:3.19 localhost:5000/alpine:3.19
$ docker push localhost:5000/alpine:3.19
```

The UI (enabled by default) will be served on **`http://localhost:8080`** so you can browse images and tags graphically.

> **TIP for LAN setups** – edit `registry/.env` to change ports, add HTTPS certs, or enable basic‑auth.

---

## ⚙️ Configuration

| Variable             | Default    | Description                              |
| -------------------- | ---------- | ---------------------------------------- |
| `REGISTRY_DATA_DIR`  | `./data`   | Where images are stored on the host.     |
| `REGISTRY_HTTP_ADDR` | `:5000`    | Listening address inside the container.  |
| `REGISTRY_AUTH`      | *disabled* | Basic‑auth; set to `htpasswd` to enable. |
| `UI_PORT`            | `8080`     | Port for the registry‑browser UI.        |

Copy `.env.sample` → `.env` and tweak as needed **before** running *docker compose*.

---

## 🧹 House‑keeping scripts

After a while registries fill up with old tags that nobody needs. The utilities in **`manage/`** help keep things tidy:

```bash
# list images & tags
python manage/list_images.py --registry http://localhost:5000

# delete tags older than 30 days, keeping the latest 5 per repo
python manage/prune_tags.py --age 30 --keep 5
```

All scripts print `--help` describing every option; they talk to the registry’s HTTP API so nothing runs inside the registry container itself.

---

## 🔒 Security notes

*For local dev the stack ships ****without authentication****.* Before exposing it outside your machine you **must**:

1. Generate TLS certificates (`certs/` folder) and set `REGISTRY_HTTP_TLS_CERT/KEY` in `.env`.
2. Enable basic authentication with `REGISTRY_AUTH=htpasswd` and create users via the provided `htpasswd.sh` helper.
3. Lock down the port on your firewall or run the stack behind an ingress controller / reverse‑proxy with AuthN.

---

## 🤝 Contributing

1. Fork the repo and create a feature branch.
2. Follow the **[Conventional Commits](https://www.conventionalcommits.org/)** style.
3. Make sure `docker compose up --build` succeeds and `pre‑commit run --all-files` passes.
4. Submit a pull request – CI will run linting and smoke tests automatically.

---

## 📜 License

This repository currently does **not** specify an open‑source license. All rights are reserved to the author.

---

> *Made with ☕ and **Docker love** by Kiran M.*
