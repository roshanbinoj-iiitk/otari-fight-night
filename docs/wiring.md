# How it is wired

```
fight.py ──► Otari (Docker, :8000) ──► Ollama (host, :11434)
   │             one scoped key per team          └─► otari.ai (optional, hosted provider)
   └── referee: makes the messy file, runs stock then yours, grades, writes the card
```

- `docker-compose.yml` runs Otari and points it at the host's Ollama.
- `otari.yml` declares the `ollama` hosted provider and the two scoped keys. You should never
  need to edit it.
- `fightnight/corrupt.py` makes golden and messy files. `fightnight/grade.py` scores. Both plain
  code, both tested.
- `fightnight/pipeline.py` runs a team file. `fightnight/team.py` validates one.
- `fightnight/otari.py` is the only code that talks to Otari: chat through the team keys, and
  an admin step before a fight that switches the models on under the provider, because a hosted
  provider declared in config starts with an empty roster. Every response's `otari-provider`
  header is what the "requests served locally" share is computed from. A timeout or gateway
  error on one request keeps those rows as they were and counts the request as failed; a
  424 or 401 (misconfiguration) stops the fight with the message.
- `fightnight/card.py` builds the card, pulling per-key usage from
  `GET /api/v1/key/usage/summary`.


## Tests

```bash
make test
```

Generator, grader, team loader, pipeline (with a fake gateway), card. No model needed.
