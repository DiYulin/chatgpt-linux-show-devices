# ChatGPT Linux: Show Other Devices

[简体中文](README.zh-CN.md)

A small, reversible companion package that keeps **Settings → Connections → Control other devices** visible in the official ChatGPT/Codex Linux desktop app.

The original app remains installed from its normal package source. This project changes one local UI visibility expression, preserves a verified original backup, and uses a Debian package trigger to reapply the change after compatible app updates.

**Experimental and unofficial.** Tested on desktop app `26.1027.30824`. Later builds are checked structurally rather than assumed compatible. Showing the entry does not establish that every remote-control workflow works on every Linux system.

## Why it exists

On an affected Linux installation, other devices could connect to the computer while its own **Control other devices** tab was hidden. Updating the app did not restore the tab. Investigation found a separate UI gate, `782640499`, whose value was inverted to decide whether to show that tab. On the investigated account and app version, the service returned a hiding value for Linux and a showing value for Windows.

This is a report about that tested configuration, not a claim about all accounts or all future releases. The local patch was applied successfully and the user confirmed that the missing entry returned.

## Install

Requirements: a Debian/Ubuntu-style system using `apt`/`dpkg`, Python 3.10 or newer, administrator access, and the official app installed at `/usr/lib/chatgpt/resources/app.asar`.

Download the `.deb` and `SHA256SUMS` from [Releases](https://github.com/DiYulin/chatgpt-linux-show-devices/releases), verify the download, then install:

```sh
sha256sum --check SHA256SUMS
sudo apt install ./chatgpt-show-other-devices_1.0.1_all.deb
```

Completely quit and reopen the desktop app. Open **Settings → Connections** and look for **Control other devices**. Pair devices using the app's normal authorization flow.

Check the actual patch result after installation:

```sh
chatgpt-show-other-devices --status
```

Look for `"enabled": true`. An unsupported app layout leaves the application unchanged; `last_result` explains why the patch was skipped. The companion package can therefore be installed even when its current app build is unsupported.

## After an app update

When `apt` or `dpkg` replaces the app archive, a registered file trigger runs the helper. If the known gate-to-UI relationship and integrity layout still match, it reapplies the patch and backs up that version's original archive. Restart the app to load the change.

If the app changes the gate, file layout, or expression structure, the helper records the reason and leaves the new app untouched. An updated helper may then be needed. Updates made outside `dpkg` do not activate this trigger.

Manual recheck:

```sh
sudo chatgpt-show-other-devices --ensure
```

## Remove and restore

```sh
sudo apt remove chatgpt-show-other-devices
```

Removal attempts to restore the matching original archive. It never replaces a newer, unrelated app build with an old backup. Completely restart the desktop app afterwards.

To delete the helper's saved state and backups too:

```sh
sudo apt purge chatgpt-show-other-devices
```

To restore temporarily while keeping the companion installed, use `sudo chatgpt-show-other-devices --restore`. A later app update can enable the UI patch again; remove the companion to disable automatic reapplication.

## What changes

- One gate-read expression in `remote-connections-settings-*.js` becomes a constant false value. Its inverse then shows the entry.
- The changed asset's SHA-256 and block hash are updated. Archive sizes and file offsets stay unchanged.
- The archive is replaced atomically, with recovery metadata saved first.
- The current original and one previous original are retained under `/var/lib/chatgpt-show-other-devices/backups/`.

The helper does not read login tokens, cookies, chats, device keys, or project files. It does not change authentication, MFA, pairing, workspace rules, or server-side access decisions. No OpenAI application binaries, assets, or archive backups are distributed in this repository or its release package. Electron executable fuses are unchanged.

See [implementation notes](docs/implementation.md) for the matching and recovery rules, and [related projects](docs/related-projects.md) for alternatives and scope comparisons.

## Build and test

No Python packages need to be installed.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_deb.py
python3 scripts/verify_package.py dist/chatgpt-show-other-devices_1.0.1_all.deb
```

The tests generate small synthetic ASAR fixtures; the official application is not required. They cover patching, repeated execution, changed asset names, update reapplication, exact restoration, backup retention, and refusing ambiguous or changed layouts.

GitHub CI also installs the helper in a clean runner, activates its package trigger, and purges it. See [CONTRIBUTING.md](CONTRIBUTING.md) for reporting compatibility results.

## License

Original project code is licensed under [MIT](LICENSE). ChatGPT, Codex, OpenAI trademarks, and upstream application code and assets remain the property of their respective owners. This project is not affiliated with or endorsed by OpenAI.
