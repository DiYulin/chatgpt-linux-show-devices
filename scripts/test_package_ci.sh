#!/bin/sh
# Exercise package lifecycle only on a disposable runner without the desktop app.
set -eu
[ "${CI:-}" = "true" ] || { echo 'Use this only on a disposable CI runner.' >&2; exit 1; }
[ ! -e /usr/lib/chatgpt/resources/app.asar ] || { echo 'Desktop app exists; refusing the CI lifecycle test.' >&2; exit 1; }
package=${1:?Pass the built .deb path}
cleanup() { sudo dpkg --purge chatgpt-show-other-devices >/dev/null 2>&1 || true; }
trap cleanup EXIT
sudo dpkg --install "$package"
chatgpt-show-other-devices --status
sudo dpkg-trigger --by-package=chatgpt-show-other-devices --no-await /usr/lib/chatgpt/resources/app.asar
sudo dpkg --triggers-only chatgpt-show-other-devices
sudo dpkg --purge chatgpt-show-other-devices
[ ! -e /usr/lib/chatgpt-show-other-devices/repair.py ]
[ ! -e /var/lib/chatgpt-show-other-devices ]
trap - EXIT
