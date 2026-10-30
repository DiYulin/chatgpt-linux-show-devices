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

## 网页要求手机扫描通行密钥二维码

标题为“通行密钥和安全密钥”、提示使用保存了 `openai.com` 通行密钥的手机或平板扫码的浏览器弹窗，是账号身份验证。手机在此负责确认身份，不是选择远程控制端或被控端。

使用保存了同一账号通行密钥的设备完成验证，或使用已绑定的实体安全密钥。之后返回 Linux 桌面客户端，在“控制其他设备”中添加目标电脑；目标电脑也需要按官方流程允许连接和完成配对。MFA、通行密钥及设备授权必须正常完成。

## English

Showing the device-control entry and authorizing the controller are separate steps. The default companion package changes UI visibility only; it does not grant hardware-device permissions.

On one test of app `26.1027.30824`, authorization failed with `cannot open Linux TPM device`. TPM 2.0 and `/dev/tpmrm0` existed, but the signed-in user lacked read/write access. After explicitly granting that user resource-manager device access, the normal authorization flow could open the browser.

Check the node and its ACL before making changes. A local administrator may explicitly grant access using the per-user ACL command above. This authorizes processes running as that user, not just ChatGPT. It does not change TPM contents or bypass authentication. A one-time ACL may not survive device recreation; persistent device policy requires a separate, explicitly reviewed local configuration and is not installed by this project's `.deb`.

A browser dialog asking for a phone that holds an `openai.com` passkey is identity verification. It does not choose the controlling device. Complete the normal passkey/security-key verification, return to the Linux desktop app, and then add the target computer using its normal pairing flow. UI visibility alone does not prove successful authorization or pairing.
