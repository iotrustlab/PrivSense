# Repository publication hygiene

The publication cleanup replaces workstation-specific paths with portable paths,
keeps API authentication in the ignored local environment, and adds an offline
privacy check:

```bash
python3 scripts/check_repo_privacy.py
python3 scripts/check_repo_privacy.py --history
```

The checker reports file locations and finding categories, never matched values.
It checks tracked files and non-ignored new files, and optionally every reachable
Git blob, for common credential formats, private-key markers, sensitive filenames,
and machine-specific absolute paths. It is a focused regression check, not a
guarantee that every possible secret format or binary metadata field is detected.
Local `.env`, datasets, generated runs, private keys, and credentials stay ignored.
The committed `.env.example` contains empty authentication fields.

Source datasets now default to `data/source/UTAH-STM-HAR`; set `PRIVSENSE_DATASET`
locally to use another location. Report output displays checkout-relative paths
or a `<local>` placeholder for directories outside the checkout.

Historical experiment hash manifests are retained unchanged: they authenticate
the artifacts used at the time of those experiments. Code and report paths edited
for this cleanup will consequently differ from those historical hashes. This is
a publication edit, not a rerun or a change to reported measurements. Frozen
dataset references use dataset-relative names; raw datasets are not redistributed.

The initial audit found workstation paths in earlier Git revisions and no matches
for the credential/private-key patterns above. The publication maintenance includes
scrubbing those workstation paths from reachable repository history and replacing
personal commit email addresses with a generic GitHub noreply identity. Author
display names are retained for attribution. Verify the
result with `--history` after the rewrite; a clean current checkout alone does not
establish that earlier revisions are clean. Historical commit and blob IDs change
when their contents are scrubbed.
