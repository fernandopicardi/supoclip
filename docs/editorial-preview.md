# Montage review before export

The editorial montage page plays the original source directly. A canvas displays
the selected foreground, optional blurred background and captions. Audio and
image come from the same video element. Playback seeks past internal cuts and
follows the chosen clip order, including repeated source occurrences.

Adjust caption font, size, position, colors, word count and highlighting. Change
clip boundaries, reorder clips, edit internal cuts, adjust each clip's framing
and correct individual caption words. Corrections apply only to that clip's
occurrence and do not change the spoken audio.

Changes stay in the browser until **Salvar montagem**. Saving validates the
whole document, preserves a checkpoint and uses a revision check. A stable
request ID lets a retry recover a successful save after a lost response. A
conflict preserves the local draft so the user can decide whether to reload.
Leaving the page discards unsaved changes; the page warns before reload/close.

**Exportar versão salva** is disabled while changes are unsaved or invalid.
Opening the page, playback and saving never enqueue a render. Previous exports
remain separate and are labeled with their revision.

The existing caption canvas renderer and font metrics are shared. Export and
preview use the same crop/scale/placement calculations and half-word inclusion
rule. Browser blur and text smoothing can differ slightly from FFmpeg/libass;
browser seeks can pause briefly at an edit. This is an interactive preview,
not a pre-encoded final file or a guarantee of sample-exact joins.

Old documents default to a black background and retain their styles. Select
**Vídeo desfocado** and save to apply the new background to a montage. Export
composes the background from the cropped foreground and burns captions last.
No schema migration or additional package is required.

Private endpoints:

- `GET /editorial/edits/{id}/preview-data`: original metadata, words and caption looks.
- `GET /editorial/sources/{id}/media`: owner-scoped media streaming with byte ranges.
- `POST /editorial/edits/{id}/draft`: document, revision and stable request ID.

Tests mock encoding. The focused browser test can read an existing local media
file via `SUPOCLIP_TEST_EXISTING_MEDIA`; it never creates a media fixture or
automatically calls the export endpoint.
