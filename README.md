# Alex E. Daley — Command Center (auto-refreshing)

A static Command Center page whose **My Tasks** card is rebuilt from Asana once a
day by a GitHub Action and committed automatically. No server, no secrets in the
page — your Asana token lives only in GitHub's encrypted secrets.

## What's in this repo

| File | Purpose |
|------|---------|
| `index.html` | The published page (GitHub Pages serves this). **Generated** — the Action overwrites it daily. |
| `command-center.base.html` | The template (everything except the live My Tasks data). Edit this if you want to change the rest of the Command Center. |
| `build.py` | Pulls your Asana tasks and rebuilds `index.html` from the template. |
| `.github/workflows/refresh.yml` | The daily scheduled job that runs `build.py` and commits the result. |

## How the data works

`build.py` reads your **incomplete tasks assigned to you**, then for each task pulls:

- **Start / Due** from the `Start Date:` / `Due Date:` Asana **custom fields** (not the native date fields).
- **Est Hrs** from the `Est. Hrs` custom field, **% Done** from the `% Done` custom field.
- **Project** from the task — or, for subtasks, from the parent task's project.

It sorts tasks into three sections — **Past Due**, **Due Today**, **In Progress** —
grouped by project and alphabetized, exactly like the inline card. Each task links
to Asana and opens in a new tab.

## The "Refresh" button

The My Tasks card header has a **Refresh** button. It opens your repo's
*Refresh Command Center* Actions page in a new tab — click **Run workflow** there to
rebuild on demand (no token in the page, safe on a public site). The button's link
is filled in automatically on the first Action run from GitHub's `GITHUB_REPOSITORY`
value, so until then it points at a `YOUR-USERNAME/YOUR-REPO` placeholder. To fix the
link before that first run (e.g. for a local build), set `REPO_SLUG=owner/repo`.

---

## One-time setup

### 1. Create the repo
Create a new GitHub repository and add all four files (keep the
`.github/workflows/` folder structure). `index.html` is already seeded with a
working snapshot, so the page works before the first scheduled run.

### 2. Get an Asana Personal Access Token
In Asana: **Profile photo → Settings → Apps → Developer console (Manage Developer
Apps) → Personal access tokens → + Create new token.** Copy it (you only see it once).

### 3. Add the token as a repo secret
In your repo: **Settings → Secrets and variables → Actions → New repository secret.**

- Name: `ASANA_TOKEN` — Value: *(paste the token)*
- *(Optional)* `ASANA_WORKSPACE_GID` — only needed if your account has more than
  one workspace and the default (your first workspace) isn't the right one.

### 4. Allow Actions to commit
**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**
(The workflow also declares `contents: write`, but this toggle must be on.)

### 5. Turn on GitHub Pages
**Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch:
`main` / `(root)` → Save.** Your page appears at the URL shown there.

### 6. Test it
**Actions → Refresh Command Center → Run workflow.** It should pull Asana, rewrite
`index.html`, and commit. After that it runs automatically every day.

---

## Changing the schedule
Edit the `cron` line in `.github/workflows/refresh.yml`. It's in **UTC**.
`0 11 * * *` = 11:00 UTC ≈ 7am US Eastern (EDT) / 6am (EST). GitHub doesn't shift
for daylight saving, so the local time moves by an hour twice a year — adjust if
you care about the exact minute.

## Running it locally (optional)
```bash
export ASANA_TOKEN=your_token_here
python build.py          # rewrites index.html
```

## Notes & limits
- The page is a **static snapshot** refreshed daily — it is not live to the second.
  Clicking any task always opens the current task in Asana.
- Project colors: `TSR84801 NPD Reduction` = orange, `FTTxx00 Static IP` = blue,
  `BSF Install Health Certificate` = green; any other project is auto-assigned from
  yellow / bold-orange / gray. To pin a new project's color, edit the `PC` map in
  the `SCRIPT` block of `build.py`.
- Keep your `ASANA_TOKEN` secret. If it's ever exposed, revoke it in the Asana
  developer console and create a new one.
