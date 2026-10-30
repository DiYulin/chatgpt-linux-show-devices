# Related projects

Surveyed on 2026-10-30. This is not the first project to investigate hidden remote-control UI. The projects below describe related work in their own repositories; their compatibility claims should be read in that context.

| Project | Related capability | Difference in scope |
| --- | --- | --- |
| [bruglet/chatgpt-desktop-linux: Remote Control UI](https://github.com/bruglet/chatgpt-desktop-linux/blob/main/linux-features/remote-control-ui/README.md) | Opt-in Linux UI gates for remote-control settings, with normal backend state preserved. | Part of a larger community desktop build and feature system. |
| [drarvindc/codex-remote-launcher](https://github.com/drarvindc/codex-remote-launcher) | A Windows launcher for the missing Control other devices flow. Its README describes runtime bridging without modifying `app.asar`. | Windows-specific launcher/runtime approach. |
| [LightHaru/chatgpt-layer](https://github.com/LightHaru/chatgpt-layer) | A general local desktop-tweak framework with install, status, and repair commands. | Broader runtime and tweak platform rather than this single Debian UI companion. |

This repository focuses on an existing official Linux package: one guarded UI expression, reversible archive replacement, and a small Debian update-trigger companion. It is an independently implemented patch, not a fork of the projects above. No code was copied from them into this implementation.
