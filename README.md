# 星萤矿安

星萤矿安项目源码，包含 WS63 固件工程、Python 数据接入/API 服务和网页数据看板。

## 目录

- `fbb_ws63/`：WS63 SDK、驱动、协议库、应用源码及开发说明。
- `fbb_ws63/vendor/developers/demo/`：项目中提供的星闪网关、串口、WiFi、MQTT 等应用。
- `ToDataBase.py`：从华为云 IoTDA 获取设备影子并写入 MySQL，同时提供网页查询接口。
- `api_server.py`：独立数据库查询 API，与前述服务按需择一运行。
- `星闪鸿蒙数据中台.html`：网页看板。
- `settings.example.json`：不含实际口令的服务配置模板。

## Python 服务

使用 Python 3.10 或更新版本安装依赖：

```powershell
python -m pip install -r requirements.txt
Copy-Item settings.example.json settings.local.json
```

在 `settings.local.json` 中填写 IoTDA 账号、项目、设备与 MySQL 连接信息。
环境变量优先于本地文件；云平台密码使用 `IOTDA_PASSWORD`，数据库密码使用
`MYSQL_PASSWORD`，独立查询服务使用 `API_DB_PASSWORD`。
数据库应准备好原程序使用的表结构，表名在配置文件中指定。

```powershell
python ToDataBase.py
```

默认服务监听5000端口；在网页中配置对应的 API 地址。`api_server.py` 也使用5000端口，
应在停止另一服务后单独启动。

## 固件

使用 HiSpark Studio 打开 `fbb_ws63/fbb_ws63-kd.hiproj`，按 SDK 说明安装 WS63
编译和烧录工具链。构建配置与应用入口见 `fbb_ws63/vendor/developers/build_config.json`，
完整 SDK 使用说明见 `fbb_ws63/README.md` 和 `fbb_ws63/tools/`。

WiFi 和 MQTT 私有配置不写入仓库。使用某个示例前，在对应源码旁将
`*.example.h` 复制为同名 `*.local.h` 并填写真实参数；本地头文件会自动被包含。
没有本地文件时使用占位配置，需填写后才能连接实际网络和云平台。

## 仓库范围

仓库保留项目源码、SDK 必要库、原始许可证和 Markdown 开发文档。
编译器安装包、构建输出、分析缓存、压缩包、大型文档、真实凭据和本地备份不上传。
本机现有设置保存在被忽略的 `settings.local.json` 和 `*.local.h` 中；
上传整理前的受影响源文件保存在被忽略的 `.publication-private/`。

第三方 SDK 与库遵循其各自许可证，见 `fbb_ws63/LICENSE`、
`fbb_ws63/LICENSE.OpenSource` 和 `fbb_ws63/COPYRIGHT.OpenSource`。
