# Troubleshooting

- **Ollama is not answering**: start it. `ollama serve` or open the app.
- **Otari cannot reach Ollama (preflight fails with 424 or a connection error) on Linux**: Ollama
  listens on 127.0.0.1 by default, which the container cannot see. Run it with
  `OLLAMA_HOST=0.0.0.0 ollama serve` (or set that in the systemd unit). Compose maps
  `host.docker.internal` to the host for you. Moved Ollama to another port? Change both
  `OLLAMA_URL` and `OLLAMA_URL_FROM_DOCKER` in `.env`.
- **Port 8000 is already in use** (`docker compose up` fails with "port is already allocated"
  or "address already in use"): pick a free port and set it in `.env` as both `GATEWAY_PORT=8001`
  and `OTARI_URL=http://localhost:8001`. The dashboard moves with it.
- **Otari did not answer within 60s**: `docker compose logs otari`. A bad `.env` stops it at
  startup.
- **424 provider_not_configured**: the model is not switched on in Otari. `make fight` does this
  for you, so run it rather than calling the API by hand.
- **Slow**: 3B models write about one row per second. `ROWS=20` for iteration, bigger batches for
  fewer round trips, smaller batches when a model loses rows. A request that passes
  `TIMEOUT_SECONDS` keeps its rows as they were and shows up as a failed request on the card.
- **Thinking models** (`qwen3`, `deepseek-r1`, hosted `gpt-oss`) spend the per-request token
  budget reasoning and get cut off. Check the "lost or garbled" column before trusting them.
- **Fresh start**: `make reset` removes the containers, the Otari database, the generated data
  and the cards. Delete `.env` too if you want new keys.
