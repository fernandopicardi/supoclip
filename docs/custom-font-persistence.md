# Persistent custom fonts in the local installation

`docker-compose.fonts.yml` mounts `supoclip_custom_fonts` at `/app/fonts/users`
in both backend and worker. Uploaded fonts survive image updates and container
recreation. Bundled fonts remain in each image and can receive upstream updates.
The existing uploads, clips, models, database and preferences are unchanged.
The volume is external to Compose. The wrapper creates it if necessary when
starting services; recreating or removing the stack does not own this volume.

Use the wrapper for local lifecycle commands so the font override is always last:

```powershell
.\scripts\compose-local.ps1 config --quiet
.\scripts\compose-local.ps1 up -d
.\scripts\compose-local.ps1 up -d --no-deps --no-build --force-recreate backend worker
```

The wrapper reuses the installed local override and any GPU/editorial overrides
that are present. These private/local configurations remain outside this change.
Do not replace the wrapper with a Compose invocation that omits the fonts overlay.
Do not remove `supoclip_custom_fonts` during updates or remove volumes with `down -v`.

## Migrating existing uploaded fonts

Before first activation, confirm there are no queued or running worker jobs or
editorial renders. Back up `/app/fonts/users` from both services. Merge their font
files into the named volume, preserving relative user directories and filenames.
If the same relative path has different contents, stop and reconcile it instead
of overwriting. Keep the backup outside the repository.

Recreate only backend and worker using the same installed images and environment.
Verify the fonts API, hashes and Portuguese glyph coverage in both services, and
then force-recreate the two services once more to test persistence. No video
generation is needed. Do not change account preferences as part of this migration.

An existing installation's manual writable-layer copies are not a durable backup.
The named volume and backups contain account-scoped font files; do not commit
their contents or authenticated configuration.

## Verification on 2026-10-28

Both services were force-recreated twice using the installed images, without
video generation. The font SHA-256 stayed unchanged and Portuguese coverage
passed in backend and worker. The API still listed the bundled NunitoSans and
the custom Caramelo font. Four editorial documents retained their revisions.
Frontend, database, Redis and transcription container IDs were unchanged.
The installed private local override also retains the same external font mount,
so its existing four-file Compose command keeps the fonts without the wrapper.
