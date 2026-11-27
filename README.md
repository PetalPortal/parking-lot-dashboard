# Parking Lot + Dashboard

A tiny, calm household console. One Python file to run, no dependencies (standard library only), data kept in plain JSON files you own.

It answers **"what would help me today?"**, not "how well am I doing?" There are no scores, streaks, grades or red/yellow/green.

## What's in it

- **Parking Lot** (`/`): a place to park ideas and errands so you can stop holding them. Parked items are "safe and waiting", never overdue. Includes a small sticker/reward ladder.
- **Dashboard** (`/dashboard`), installable to a phone home screen:
  - **Small Win + Stars**: one line for today's small win, and up to three stars a day (one for the day, two for things you choose). Stars are only ever added. Empty days are a faint outline.
  - **One gentle thing**: one small suggestion a day from a list you can edit. Do it, swap it, or skip it. Skipping is fine.
  - **Notes**: leave notes and questions for the owner, who can answer, save for later, or tuck them away. Notes can offer a star, and only the owner places it.
  - **Parking Lot count**: how many items are waiting.
  - **Weather** (optional): 7-day forecast from [Open-Meteo](https://open-meteo.com/) (no account or key).
  - **Sleep & Body** (optional): read-only Oura summary through an adapter you write yourself.
  - **Calm mode**: a flat, dim, motionless version for migraine or overwhelm days. Nothing animates.

## Run it

```
python park_server.py serve
```

Then open `http://localhost:8765/dashboard`. Copy `config.example.json` to `config.json` to change anything.

```
python park_server.py add "buy lightbulbs"     # add an item from the command line
python park_server.py list
```

### Settings (`config.json`)

- `data_dir`: where your JSON files live. Default `data/` (created on first use).
- `port`: default 8765.
- `owner_name`, `helper_name`: optional, used for the greeting and notes title.
- `weather`: set `enabled: true` plus your `latitude`, `longitude`, `place` and `timezone`. Use a nearby city, not your street address.
- `oura_adapter`: path to your own Python file exposing `api(path, params)`. See `oura_adapter.example.py`. Leave empty to hide the tile.

## Security: please read

**There is no password.** Anyone who can reach the port can read and change everything.

- Run it only on a private network (home Wi-Fi) or a private VPN such as Tailscale.
- **Never expose it to the public internet** (no port forwarding, no public tunnel).
- The data is your personal notes, wins and (if enabled) health summaries. Keep `data/` and `config.json` out of version control. The included `.gitignore` already does.
- Keep Oura or other tokens in your own adapter file, never in this repo.
- Do not share screenshots of the dashboard if they contain private notes or health numbers.

## Design rules (please keep them if you extend it)

1. Information, never a verdict. Low numbers mean "go gentle", not "warning".
2. Add-only rewards. No removing stars, no streak counters, no "you missed".
3. Everything optional can be skipped without consequence.
4. Calm mode must quiet every animated element.
5. Integrations are read-only.

## Notes

- Works on Python 3.9+. Tested on Windows.
- Data files are written atomically (temp file then rename).
- Phone install: iOS Safari Share, then Add to Home Screen. Android Chrome menu, then Install app.
- The server is single-user by design. It is not hardened.

MIT licensed.
