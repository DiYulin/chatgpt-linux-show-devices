# 授权与 TPM 排查 / Authorization and TPM troubleshooting

显示“控制其他设备”与成功授权是两个不同步骤。本项目的默认辅助包只处理前者，不自动授予硬件设备权限。

## `cannot open Linux TPM device`

在客户端 `26.1027.30824` 的一次实际测试中，点击网页授权前，桌面日志连续报告此错误。机器存在 TPM 2.0 和 `/dev/tpmrm0`，但当前用户没有这个字符设备的读写权限。只修正该用户的设备访问权限后，授权流程便能够正常打开浏览器。

权限初检可以使用：

```sh
ls -l /dev/tpmrm0
getfacl -p /dev/tpmrm0
test -r /dev/tpmrm0 && test -w /dev/tpmrm0 && echo "device permissions available"
```

如果设备存在但缺少权限，应由本机管理员审核并配置访问策略。为当前用户添加资源管理设备 ACL 的示例为：

```sh
sudo setfacl -m "u:$(id -u):rw" /dev/tpmrm0
```

该命令把访问权限授予当前用户的进程，并非只授予 ChatGPT。它不修改 TPM 内容、密钥、MFA 或远程授权结果；这项单次 ACL 也可能在设备重建或重启后消失。执行前应记录原 ACL，以便撤销自己的修改而不覆盖其他用户的条目。

若需要持久化，可由管理员创建仅匹配所选资源管理设备、给明确本地 UID 设置 ACL 的 udev 规则，并验证设备事件后的实际权限。策略取决于本机账户与硬件配置，因此默认 `.deb` 不安装此类权限规则，也不把用户自动加入硬件访问组。

设备不存在、TPM 不可用或后续出现其他密钥错误时，单纯调整 ACL 不足以解决。此时应保留具体错误，分别排查硬件、操作系统策略和客户端支持情况。

### 可选的持久化工具

源码中的 [`scripts/tpm_user_access.py`](../scripts/tpm_user_access.py) 整理自此次实际修复，**独立于默认 `.deb`，不会自动运行**。使用前应先由管理员审核。它给明确指定的一个非 root 本地用户授权，不是仅给某个应用授权。

额外要求：`/usr/bin/getfacl`、`/usr/bin/setfacl`（Debian/Ubuntu 的 `acl` 包）、`udevadm` 254 及以上，以及可用的 `/dev/tpmrm0`。默认 UI 辅助包不要求这些额外条件。脚本保留现有共享 ACL mask；如果 mask 或基础 group 权限不允许读写，会拒绝修改，交由管理员审核。

在仓库目录中，以准备使用客户端的普通用户执行检查和规则预览：

```sh
python3 scripts/tpm_user_access.py --user "$(id -un)" --check
python3 scripts/tpm_user_access.py --user "$(id -un)" --preview-rule /tmp/chatgpt-tpm-preview.rules
cat /tmp/chatgpt-tpm-preview.rules
```

确认要授予该用户访问权限后，应用并再次检查：

```sh
sudo python3 -I scripts/tpm_user_access.py --user "$(id -un)" --apply
python3 scripts/tpm_user_access.py --user "$(id -un)" --check
```

它保存该用户的原 ACL 条目至 `/var/lib/chatgpt-tpm-user-access/`，安装 `/etc/udev/rules.d/72-chatgpt-tpm-user-access.rules`，并验证设备事件后的访问权限。检查只尝试打开并关闭资源管理设备，不发送 TPM 协议命令；脚本不访问原始 `/dev/tpm0`，也不读取登录凭据。仅维护一个用户的规则，重复应用会保留首次记录的恢复信息。

撤销此项可选修改：

```sh
sudo python3 -I scripts/tpm_user_access.py --user "$(id -un)" --restore
```

撤销时删除它维护的规则、恢复该用户原 ACL 条目，并保留其他条目和共享 mask。它不会用整份旧 ACL 覆盖后来修改的权限；若原来没有扩展 ACL，撤销后可能保留不改变有效权限的 mask 条目。卸载 UI 辅助包不会自动撤销这个单独启用的工具，应分别操作。

## 网页要求手机扫描通行密钥二维码

标题为“通行密钥和安全密钥”、提示使用保存了 `openai.com` 通行密钥的手机或平板扫码的浏览器弹窗，是账号身份验证。手机在此负责确认身份，不是选择远程控制端或被控端。

使用保存了同一账号通行密钥的设备完成验证，或使用已绑定的实体安全密钥。之后返回 Linux 桌面客户端，在“控制其他设备”中添加目标电脑；目标电脑也需要按官方流程允许连接和完成配对。MFA、通行密钥及设备授权必须正常完成。

## `State mismatch` 与 `expired enrollment challenge`

在本次排查中，TPM 权限修正后，日志显示身份验证和设备挑战签名已通过，随后服务端返回 `expired enrollment challenge`。这说明最初申请的设备登记挑战已经过期，不表示 TPM 权限又失效。挑战有效期由服务端决定，本项目不修改它。

客户端浏览器回调中的 `State mismatch` 表示返回的状态值与当前等待的授权请求不一致。重复发起授权后再使用旧网页或旧回调，可能出现这种情况；它与“入口是否显示”是不同问题。

重新完成一次流程：

1. 关闭先前打开的授权网页。
2. 完全退出桌面客户端，再重新打开。
3. 进入“设置 → 连接 → 控制其他设备”，发起一次新授权。
4. 只使用这次新打开的网页，及时完成正常身份验证并返回客户端。

本次用户在重新尝试后报告问题已解决。此结果来自一台机器的一次排查，不能作为所有设备均可成功配对的保证。若仍失败，应记录新的错误和客户端版本；无需仅因旧授权回调失效就重装 UI 补丁。反馈时不要上传完整回调网址、验证码、令牌或设备密钥。

## English

Showing the device-control entry and authorizing the controller are separate steps. The default companion package changes UI visibility only; it does not grant hardware-device permissions.

On one test of app `26.1027.30824`, authorization failed with `cannot open Linux TPM device`. TPM 2.0 and `/dev/tpmrm0` existed, but the signed-in user lacked read/write access. After explicitly granting that user resource-manager device access, the normal authorization flow could open the browser.

Check the node and its ACL before making changes. A local administrator may explicitly grant access using the per-user ACL command above. This authorizes processes running as that user, not just ChatGPT. It does not change TPM contents or bypass authentication. A one-time ACL may not survive device recreation; persistent device policy requires a separate, explicitly reviewed local configuration and is not installed by this project's `.deb`.

A browser dialog asking for a phone that holds an `openai.com` passkey is identity verification. It does not choose the controlling device. Complete the normal passkey/security-key verification, return to the Linux desktop app, and then add the target computer using its normal pairing flow. UI visibility alone does not prove successful authorization or pairing.

### Optional persistent TPM access

The source-only [`scripts/tpm_user_access.py`](../scripts/tpm_user_access.py) is an explicit administrator tool, separate from the `.deb`. It requires the `acl` tools, `udevadm` 254 or newer, and an available `/dev/tpmrm0`. Run it from the repository as the intended non-root user, using the commands above: `--check`, `--preview-rule FILE.rules`, then an administrator-approved `--apply`. Use `--restore` to undo its rule and restore the selected user's original ACL entry. Removing the UI package does not undo this separately enabled tool.

This grants access to that user's processes. It preserves the shared ACL mask and refuses a mask/group policy that lacks read/write access. It does not send TPM commands, access the raw TPM node, read credentials, or alter authentication. Recovery changes only the selected user's entry, preserving other entries and the shared mask; a harmless mask entry may remain when the original ACL had none. Rule and recovery paths are listed above. Tests exercise ACL changes on temporary ordinary files, not TPM hardware.

### Stale authorization requests

On the investigated machine, normal identity verification and device-challenge signing succeeded, but the server then rejected the enrollment with `expired enrollment challenge`. The server controls that challenge's lifetime. A callback reporting `State mismatch` has a state value different from the client's pending authorization request; using an old page after starting another request is one possible cause.

Close old authorization pages, fully quit and reopen the desktop app, start one fresh authorization from **Control other devices**, and promptly finish verification using only the newly opened page. The user reported that the issue was resolved after retrying. This is a single-machine result, not a compatibility guarantee. Keep the state, account, MFA, and challenge checks intact. If the problem persists, report the new error and app version without callback URLs, codes, tokens, or keys.
