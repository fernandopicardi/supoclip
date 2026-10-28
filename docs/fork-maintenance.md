# Maintaining the personalized fork

`origin` points to `fernandopicardi/supoclip`; `upstream` points to
`FujiwaraChoki/supoclip`. The `caramelo` branch preserves the personalized
baseline. Keep upstream `main` available independently.

## Extensions to preserve

- Optional local Whisper service, bounded concurrency and native JSON output
  for supported local Ollama models.
- Directed source preparation, paginated transcripts, occurrence-specific cuts,
  revision checks, checkpoints and immutable exports through MCP.
- Private montage discovery and editorial review pages.
- Shared persistent custom fonts; see [font persistence](custom-font-persistence.md).

Keep extensions in separate commits. Preserve upstream license and authorship.
Do not publish credentials, account fonts, recordings, transcripts or private
session reports. Git is not a backup of the installation's persistent volumes.

## Upstream updates

1. Fetch `upstream` without changing the live installation.
2. Review the commits and changed files against `caramelo`.
3. Create an isolated upgrade branch/worktree from `caramelo`, then merge the
   chosen upstream revision there. Resolve conflicts without dropping local
   behavior or replacing saved editorial documents.
4. Validate backend/MCP contracts, frontend types, dependencies, authentication,
   caption controls and persistent volumes using synthetic fixtures.
5. Review before merging into `caramelo`. Rebuilding or restarting the live
   installation is a separate release step.

Use worktrees under `C:\worktrees\supoclip` and physical dependencies exclusive
to each checkout. Use the pnpm version declared in `frontend/package.json` and
the frozen lockfile. Never share node_modules. A code check does not authorize
video generation; test renders also need an approved editorial proposal.

## Editorial baseline

The approved reference is Nunito Sans, white `#FFFFFF`, and 24 px in settings.
Choose caption position per video. Send the selected spoken text, sequence,
omissions, estimated duration and presentation before creating or revising a
video; only render after approval. The per-video editor already has vertical
position controls. Position presets, dragging text, and dynamic font choices in
the directed editor are separate changes, not part of this consolidation.
