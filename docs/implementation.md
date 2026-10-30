# Implementation and compatibility

The default target is `/usr/lib/chatgpt/resources/app.asar`. Only the official app identity `openai-codex-electron` and one `webview/assets/remote-connections-settings-*.js` asset are accepted.

The helper requires all of the following before preparing a change:

1. One assignment reads the known gate `782640499`.
2. One variable directly inverts that value.
3. That inverted variable is passed as `showControlOtherDevices`.
4. The expected device-control UI text is present.
5. The target asset has the expected, valid single-block SHA-256 metadata.
6. Replacing the expression and its two hash references leaves all unrelated archive metadata unchanged.

The gate-read expression is replaced by a padded constant false expression. Its inverse then allows the local entry to show. A fresh file is prepared beside the archive, checked, backed up, and installed with an atomic rename. Sizes and offsets are preserved. No debugger, inspector endpoint, account token, or network API is needed by the distributed helper.

The Debian `interest-noawait` trigger watches the archive path. Trigger failures are recorded without failing the main app's package update. `--status` reports whether the current archive hash matches the last successfully patched hash, along with the most recent result.

`state.json` records the original hash, patched hash, version, asset, and backup path. Recovery information is saved before replacement, so interruption before the rename leaves the original intact and a later run can retry. Only the helper's own backup directory is pruned; it retains the current original plus one previous original. Removal restores only an exact matching patched archive.

The helper can adopt the original locally tested `26.1027.30824` patch when its exact full hash and verified original backup match. Those hashes identify application bytes, not account or device data. The repository distributes neither archive.

## Validation scope

Desktop app `26.1027.30824` on one Debian/Ubuntu-family Linux installation was tested manually: the missing entry returned after restarting the app. The persistent companion's trigger was activated and its already-enabled state verified. Broader pairing and platform compatibility is not asserted.

Unit tests use generated archives to test update reapplication, minified variable and asset-name changes, repeatability, exact restoration, backup retention, invalid integrity metadata, duplicate matches, changed UI relationships, and symbolic links. CI additionally exercises installing, triggering, and purging the companion package without an upstream app installed.

If upstream removes this gate or changes the structural relationship, prefer leaving the official app intact until a new layout has been reviewed and covered by fixtures.
