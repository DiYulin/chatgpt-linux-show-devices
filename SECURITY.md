# Security

This tool writes a root-owned application archive and runs from a Debian package trigger. Review the source and package before installing it. It is an unofficial local modification and can stop matching after upstream changes.

The intended boundary is one UI visibility expression. Authentication, MFA, pairing, remote-host authorization, Electron executable fuses, and server decisions are outside this project's scope.

The optional source-only `scripts/tpm_user_access.py` is separate from the UI package. An administrator can explicitly grant one local user access to `/dev/tpmrm0` and persist it with a udev rule. This grants access to processes running as that user, not just the desktop app. The tool preserves the shared ACL mask, refuses unrelated rules, saves the selected user's original entry, and provides restoration. It never sends TPM commands or bypasses identity or enrollment checks. See [authorization troubleshooting](docs/authorization-troubleshooting.md) before choosing to use it.

Please use GitHub private vulnerability reporting when available for vulnerabilities in this helper. Do not publish credentials, account data, device keys, proprietary application archives, or exploit details that expose other users. Ordinary compatibility reports can be public.

The helper validates its target layout and asset integrity, uses root-owned state, keeps verified original backups, and declines unknown layouts. These checks reduce accidental changes; they are not a general verification of every upstream application file.
