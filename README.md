# Alex E. Daley — Command Center (auto-refreshing)

A static Command Center page whose **My Tasks** card is rebuilt from Asana once a
day by a GitHub Action and committed automatically. No server, no secrets in the
page — your Asana token lives only in GitHub's encrypted secrets.

## What's in this repo

| File | Purpose |
|------|---------|
| `index.html` | The published page (GitHub Pages serves this). **Generated** — the Action overwrites it daily. |
| `command-center.base.html` | The template (everything except the live My Tasks data). Edit this to change the rest of the Command Center. |
| `build.py` | Pulls your Asana tasks + portfolios and rebuilds `index.html` from the template. |
| `.github/workflows/refresh.yml` | The daily scheduled job that runs `build.py` and commits the result. |

## Page layout

- **Left column:** Branding, Education, Mental Health Platform, Memoir, Work Search
- **Right column:** Current Clients, My Tasks
- **Full-width band:** Tools

## How the My Tasks data works

`build.py` reads your **incomplete tasks assigned to you**, then for each task pulls:

- **Start / Due** from the `Start Date:` / `Due Date:` Asana **custom fields** (not the native date fields).
- **Est Hrs** from `Est. Hrs`, **% Done** from `% Done` (custom fields).
- **Project** from the task — or, for subtasks, from the parent task's project. Subtasks also show their **parent task** in gray above the task name.
- **Portfolio (client)** — each project's portfolio is looked up from Asana and shown as a colored tag in the project header (Brightspeed = orange, Cyclotron = lavender). Add more in the `PORTCOL` map in `build.py` if you create new client portfolios.

Tasks are split into **Past Due**, **Due Today**, **In Progress**, grouped by project
and alphabetized. Each task links to Asana and opens in a new tab.

## The "Refresh" button

The My Tasks card header has a **Refresh** button. It opens your repo's
*Refresh Command Center* Actions page in a new tab — click **Run workflow** there to
rebuild on demand (no token in the page, safe on a public site). The link is filled
in automatically on the first Action run from GitHub's `GITHUB_REPOSITORY` value, so
until then it points at a `YOUR-USERNAME/YOUR-REPO` placeholder. To fix it before that
first run (e.g. for a local build), set `REPO_SLUG=owner/repo`.

---

## One-time setup

1. **Create the repo** and add all the files (keep the `.github/workflows/` folder
   structure). `index.html` is already seeded with a working snapshot.
2. **Get an Asana Personal Access Token:** Asana → profile photo → Settings → Apps →
   Developer console → Personal access tokens → Create new token. Copy it.
3. **Add the token as a repo secret:** repo → Settings → Secrets and variables →
   Actions → New repository secret. Name `ASANA_TOKEN`, value = the token.
   *(Optional)* `ASANA_WORKSPACE_GID` if you have more than one workspace.
4. **Allow Actions to commit:** Settings → Actions → General → Workflow permissions →
   Read and write permissions → Save.
5. **Enable GitHub Pages:** Settings → Pages → Deploy from a branch → `main` / `(root)`.
6. **Test:** Actions → Refresh Command Center → Run workflow. After that it runs daily.

## Schedule
`cron: "0 11 * * *"` in the workflow = 11:00 UTC ≈ **7am US Eastern (EDT)** / 6am (EST).
GitHub cron doesn't shift for daylight saving. Edit that line (UTC) to change it.

## Running locally (optional)
```bash
export ASANA_TOKEN=your_token_here
export REPO_SLUG=your-username/your-repo   # makes the Refresh button link correct
python build.py
```

## Notes & limits
- The page is a **daily snapshot**, not live-to-the-second. Every task always links to
  the current task in Asana.
- Project colors: TSR84801 = orange, FTTxx00 = blue, BSF = green; other projects auto-
  pick yellow / bold-orange / gray. Edit the `PC` map in `build.py` to pin colors.
- Keep `ASANA_TOKEN` secret. If exposed, revoke it in the Asana developer console.
