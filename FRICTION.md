# Friction log

Machine: Linux 6.18 (Arch LTS kernel), 16 GB RAM, RTX 3050 Laptop 4 GB VRAM. Ollama 0.34.4,
Docker Compose 5.5.1, uv 0.13.8, GNU Make 4.4.1.

## Setup

1. **Ollama not reachable from the container by default on Linux.** The packaged Ollama binds
   to 127.0.0.1, and nothing in `make fight` checks this up front; the fix lives in
   docs/troubleshooting.md. Started it with:
   `OLLAMA_HOST=0.0.0.0 ollama serve`
2. **Docker daemon was not running.** `docker ps` -> `Cannot connect to the Docker daemon at
   unix:///var/run/docker.sock`. Fixed with `systemctl start docker`. Expected on a laptop
   that does not autostart Docker, but `make fight` would have failed at `docker compose up`.
3. qwen2.5:3b pulled fine, digest `357c53fb659c` (official). `ollama ps` after one call:
   `2.2 GB  100% GPU`, so a single 3B model fits in 4 GB VRAM.
