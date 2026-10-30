# Changelog

## Unreleased

- Add separate, opt-in TPM access tooling with a persistent per-user rule, guarded restoration, and temporary-file ACL tests; the default Debian package does not install it.
- Document passkey verification, expired enrollment challenges, and fresh-request recovery for `State mismatch`.
- Use Chinese as the default README and keep an independent English version.

## 1.0.1

- First public source release with English and Simplified Chinese documentation.
- Debian companion package with automatic file-trigger reapplication.
- Atomic archive replacement, SHA-256 metadata updates, original backup retention, and guarded restoration.
- Compatibility checks for the known UI-only gate relationship.
- Synthetic archive tests and package lifecycle CI.
