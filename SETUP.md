# Getting this onto GitHub

Run these from inside the unzipped folder.

## 1. Verify it runs before you publish anything

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    export DBT_PROFILES_DIR=.
    python ingest/load_raw.py --source fixture
    dbt build
    python ingest/reconcile.py

You should see `PASS=30 ... ERROR=0`. If that is green, the repo is publishable.

## 2. Create the repo

    git init -b main
    git add .
    git commit -m "Inherited service-level script, untested"

Make the first commit the legacy state only, if you want the history to tell
the story. Simpler alternative: commit everything at once and let the README
carry the narrative. Both are defensible; the second is faster.

Then, on github.com, create an empty public repo named `nl-transit-dbt` with
no README, no .gitignore, no licence. GitHub will show you the remote URL.

    git remote add origin https://github.com/<you>/nl-transit-dbt.git
    git push -u origin main

## 3. Confirm CI goes green

Actions runs on push to main. Open the Actions tab and watch `dbt build`.
The first run will be slower — it installs the spatial extension.

If it fails, the two likely causes are a missing `DBT_PROFILES_DIR` (it is set
in the workflow env block) and Python version drift.

## 4. Work in branches from here

    git checkout -b feat/stop-buurt-join
    # edit models
    dbt build --select int_stop_buurt+
    git add . && git commit -m "..." && git push -u origin feat/stop-buurt-join

Open the pull request in the browser. Let CI run. Merge only on green.

The pull requests are the artefact. A reviewer reads them to see how you work,
which is a thing a folder of SQL files cannot show.

## 5. Turn the spatial extension back on

`profiles.yml` has the `extensions:` block commented out, because the machine
this scaffold was built on could not reach the DuckDB extension server. Your
laptop and GitHub Actions both can. Uncomment it on day three, before writing
`int_stop_buurt`.
