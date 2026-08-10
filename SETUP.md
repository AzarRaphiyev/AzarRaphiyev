# Setup — the parts that need your hands

Everything else is generated. These four need your account, so I could not do them.

## 1. The snake — already working, nothing to do

Both runs of `Generate contribution snake` went green on the first push and the
`output` branch now holds `snake-dark.svg` and `snake-light.svg`. The README
points at them and the workflow re-runs every 12 hours.

If a future run ever fails at the push step, the fix is:
**Repo** Settings → Actions → General → Workflow permissions → **Read and write
permissions** → Save. That is *this repository's* settings, not your account
settings — they look almost identical and the account-level one will not fix a
failing workflow.

## 2. Self-host the stats cards — required, not optional

The stats and top-languages cards are commented out in `README.md`, because the
shared public instance of github-readme-stats is currently **down**, not just
busy:

```
$ curl -s -o /dev/null -w '%{http_code}' https://github-readme-stats.vercel.app/api?username=AzarRaphiyev
503     # "The deployment is currently unavailable — DEPLOYMENT_PAUSED"
```

Even when it is up, thousands of profiles share it and it regularly answers
`API rate limit exceeded`. Your own Vercel instance is free and has its own rate
budget. The streak card is a different service and works already.

1. **Create a classic token** — Settings → Developer settings → Personal access
   tokens → **Tokens (classic)** → Generate new token (classic) → scope `repo`
   → expiration **No expiration**.
   Copy it immediately; GitHub never shows it again. Never paste it into a repo,
   an issue, or a chat — it grants full access to your repositories.
2. **Fork** `anuraghazra/github-readme-stats`.
3. **Vercel** — sign up with GitHub → Hobby (free) → Add New Project → import
   the fork.
4. Add environment variable `PAT_1` = your token → **Deploy**.
5. Take the instance URL Vercel gives you (`https://<something>.vercel.app`),
   put it in `tools/readme.py` as `STATS_HOST`, then:

   ```bash
   python tools/readme.py
   ```

   then uncomment the `STATS` block in the regenerated `README.md` and commit.

`hide_rank=true` is deliberate: the rank grade is weighted by stars received,
so an account whose work lives in coursework and client repos scores as though
it had shipped nothing. The commit and contribution numbers are the honest part
of that card.

## 3. Regenerating the banner

The SVGs are build output. The source of truth is `tools/` plus the `.npy` data
in `tools/_data/`.

```bash
python -m pip install pillow numpy scipy matplotlib simpleicons
python tools/banner.py
```

To use a different photo: drop it at `tools/source-photo.jpg`, then re-check the
crop and the background threshold with

```bash
python tools/01_explore_mask.py
```

which writes candidate masks to `tools/_debug/`. A flat, evenly lit backdrop is
what makes the dark-mode cut-out clean — that choice matters more than anything
in the generator.
