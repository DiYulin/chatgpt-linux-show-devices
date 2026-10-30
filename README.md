# ChatGPT Linux：显示“控制其他设备”

[English](README.en.md)

给官方 ChatGPT/Codex Linux 桌面客户端安装一个小型、可回滚的补丁，恢复 **设置 → 连接 → 控制其他设备** 入口，并在兼容的客户端更新后自动重新应用。

保留官方客户端及其正常更新来源。安装包仅包含本项目的修补代码，不包含 OpenAI 客户端、`app.asar`、账号数据或原文件备份。

**实验性、非官方项目。** 已在客户端 `26.1027.30824` 上确认入口恢复。后续版本会进行结构校验，不能保证所有新版都兼容，也不能仅凭显示入口就保证所有远程操作都能成功。

## 问题来源

在最初排查的设备上，Windows 能连接 Linux，但 Linux 缺少“控制其他设备”标签，更新客户端后仍然如此。排查发现，客户端单独读取一个控制入口隐藏的开关 `782640499`。在当时测试的同一账号和版本下，服务端针对 Linux 和 Windows 返回了不同的隐藏值。

本项目只修改本地界面显示判断；账号授权、MFA、设备配对和服务端权限仍然按原流程执行。上述现象来自实际测试，不代表所有账号或后续版本都采用相同配置。

## 安装

适用范围：使用 `apt`/`dpkg` 的 Debian/Ubuntu 系统、Python 3.10 及以上、管理员权限，以及安装在 `/usr/lib/chatgpt/resources/app.asar` 的官方客户端。

从[发布页](https://github.com/DiYulin/chatgpt-linux-show-devices/releases)下载 `.deb` 和 `SHA256SUMS`，校验后安装：

```sh
sha256sum --check SHA256SUMS
sudo apt install ./chatgpt-show-other-devices_1.0.1_all.deb
```

完全退出并重新打开客户端，进入“设置 → 连接”，再按正常流程添加、授权和配对其他设备。

检查实际是否启用：

```sh
chatgpt-show-other-devices --status
```

`"enabled": true` 表示补丁已经生效。若新版不兼容，客户端会保持原样，`last_result` 会记录跳过原因；辅助包安装成功不等于一定匹配当前客户端。

若入口出现后仍然“远程控制授权失败”，请看[授权与 TPM 排查](docs/authorization-troubleshooting.md)。已观察到当前用户无法访问 `/dev/tpmrm0` 导致授权失败的情况。网页上的手机扫码也可能只是通行密钥身份验证，并不表示只能由手机控制电脑。

## 更新后的行为

系统通过 `apt` 或 `dpkg` 更新客户端时，辅助包的文件触发器会自动运行。只有已确认的开关、界面关联及校验结构仍然匹配时，才会备份并重新应用补丁。更新后重启客户端生效。

如果新版改了相关结构，修补程序会保留新版原样并记录原因，可能需要更新本辅助包。直接复制文件等绕过 `dpkg` 的更新方式不会触发自动修补。

手动重新检查：

```sh
sudo chatgpt-show-other-devices --ensure
```

## 撤销和恢复

```sh
sudo apt remove chatgpt-show-other-devices
```

卸载时尝试恢复与当前补丁对应的原文件；如果客户端已经被更新成其他内容，不会拿旧备份覆盖新版。完成后重启客户端。

删除辅助包自己的状态和备份：

```sh
sudo apt purge chatgpt-show-other-devices
```

如仅需临时恢复，可执行 `sudo chatgpt-show-other-devices --restore`。辅助包仍安装时，后续更新可以再次应用补丁；永久停用应卸载辅助包。

## 实现范围

- 仅将连接设置中的一个隐藏开关读取表达式固定为关闭。
- 更新被改动文件的 SHA-256 与分块校验值，保持文件长度和归档偏移不变。
- 保存恢复信息后原子替换归档，保留当前版本和上一个版本的原文件备份。
- 不读取登录令牌、Cookie、聊天、设备密钥或项目文件，不修改 Electron 可执行文件的开关。

备份和状态保存在 `/var/lib/chatgpt-show-other-devices/`。详见[实现说明](docs/implementation.md)和[相关项目](docs/related-projects.md)。

## 开发

无需安装额外 Python 包：

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_deb.py
python3 scripts/verify_package.py dist/chatgpt-show-other-devices_1.0.1_all.deb
```

测试使用生成的 ASAR 样例文件，不需要官方客户端。CI 额外验证 Debian 包的安装、触发器调用及卸载。兼容性反馈请见[贡献指南](CONTRIBUTING.md)。

本项目原创代码采用 [MIT](LICENSE) 许可证。与 OpenAI 无关联，也未获其背书。
