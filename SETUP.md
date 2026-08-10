# Setup — the parts that need your hands

Everything else is generated. These four need your account, so I could not do them.

## 1. Let the snake Action write to the repo

**Repo** Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save.

This is *this repository's* settings, not your account settings — they look almost
identical and the account-level one will not fix a failing workflow.

Until this is set, `Generate contribution snake` fails at the push step.

## 2. Turn the snake on

The workflow writes two SVGs to an `output` branch. That branch does not exist
until the first run finishes, so the README ships with the snake block commented
out — otherwise GitHub caches the 404 and the image stays broken for hours.

After the Action shows green (Actions tab), delete the `<!--` / `-->` around the
SNAKE block in `README.md` and commit.

## 3. Self-host the stats cards

`README.md` currently points at the shared public instance of
github-readme-stats. Thousands of profiles hit it, so it regularly answers
`API rate limit exceeded` and your cards render as an error box. Your own Vercel
instance is free and has its own rate budget.

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

   and commit the regenerated `README.md`.

`hide_rank=true` is deliberate: the rank grade is weighted by stars received,
so an account whose work lives in coursework and client repos scores as though
it had shipped nothing. The commit and contribution numbers are the honest part
of that card.

## 4. Regenerating the banner

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
