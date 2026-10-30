# Contributing

Run `python3 -m unittest discover -s tests -v` before submitting a change. Add a synthetic fixture that demonstrates a new supported layout and a nearby incompatible layout that must be left untouched.

Install the distribution's `acl` package to run the optional TPM-tool tests too; those tests are skipped when `getfacl` or `setfacl` is unavailable. They operate only on temporary files and mocked udev calls, without administrator access, the desktop app, or TPM hardware. Cover restoration and preservation of other ACL entries when changing that tool.

For compatibility reports, include the desktop app version, distribution, installation path, helper version (`dpkg-query -W chatgpt-show-other-devices`), whether the entry appears after a full restart, and the redacted `last_result` from `chatgpt-show-other-devices --status`.

Report UI visibility and actual device pairing separately. A visible tab alone is not proof of successful remote control.

Do not attach `auth.json`, tokens, cookies, device keys, chat history, application archives, proprietary JavaScript bundles, or project files. A minimal synthetic reproduction is preferred. Do not remove matching or integrity checks to accommodate an unknown application layout.

Use the issue tracker for ordinary compatibility failures. See [SECURITY.md](SECURITY.md) for security reports.
