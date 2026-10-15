# Publishing the project page

The project page is `docs/site/index.html`. The `Pages` workflow (`.github/workflows/pages.yml`) deploys it on every push to `main` that changes `docs/site/`.

## One-time setup

GitHub Pages must be set to deploy from GitHub Actions. The workflow can't switch Pages on by itself with the default `GITHUB_TOKEN`.

```bash
gh api -X POST repos/VinayakMokashi/filings-research-copilot/pages -f build_type=workflow
gh api repos/VinayakMokashi/filings-research-copilot/pages --jq .build_type   # prints: workflow
```

The same setting in the web UI is **Settings > Pages > Build and deployment > Source > GitHub Actions**.

If Pages was enabled after a push, that push's Pages run has already failed. Re-run it, so that commit's check turns green:

```bash
gh run rerun $(gh run list --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

## Redeploy without a code change

```bash
gh workflow run pages.yml
```

## Verify

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://vinayakmokashi.github.io/filings-research-copilot/   # 200
```

Allow about a minute after the deploy job finishes.
