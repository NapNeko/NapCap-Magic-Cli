# -*- coding: utf-8 -*-
# 标准库导入
import io
import os
import re
import sys
import json
import time
import curses
import zipfile
import argparse
import platform
import subprocess
import dataclasses
from enum import Enum
from pathlib import Path

# 检查 Python 版本是否符合要求, 如果低于版本 3.8 则退出
if sys.version_info < (3, 9):
    sys.exit("安装 NapCat 需要 Python 3.9 或更高版本")

# 获取当前系统信息
arch = platform.machine().lower()


class PackInstaller(Enum):
    # 定义包安装器枚举
    RPM = "rpm"
    DPKG = "dpkg"

    def __str__(self):
        return self.value


class PackManager(Enum):
    # 定义管理器枚举
    APT_GET = "apt-get"
    YUM = "yum"

    def __str__(self):
        return self.value


class DownloadSuffix(Enum):
    # 定义下载链接后缀枚举
    AMD64_DEB = "_amd64.deb"
    AMD64_RPM = "_x86_64.rpm"
    ARM64_DEO = "_arm64.deb"
    ARM64_RPM = "_aarch64.rpm"

    def __str__(self):
        return self.value


# 定义 ANSI 终端前景色的 ANSI 码
FOREGROUND_COLORS = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "pink": 35,
    "gray": 90,
    "dark_gray": 40,
}

# 定义终端输出 NapCat Install Logo
LOGO = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                                                                              ║
║           ███╗   ██╗  █████╗  ██████╗   ██████╗  █████╗  ████████╗           ║
║           ████╗  ██║ ██╔══██╗ ██╔══██╗ ██╔════╝ ██╔══██╗ ╚══██╔══╝           ║
║           ██╔██╗ ██║ ███████║ ██████╔╝ ██║      ███████║    ██║              ║
║           ██║╚██╗██║ ██╔══██║ ██╔═══╝  ██║      ██╔══██║    ██║              ║
║           ██║ ╚████║ ██║  ██║ ██║      ╚██████╗ ██║  ██║    ██║              ║
║           ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚═╝       ╚═════╝ ╚═╝  ╚═╝    ╚═╝              ║
║                                                                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


def _echo_logo() -> None:
    """
    ## 绘制一个 Logo
    """
    os.system("clear")
    _echo(LOGO)


def _echo(text: str, end: bool = True) -> None:
    """
    ## 输出文本内容到标准输出，添加换行符
    """
    sys.stdout.write(text + ("\n" if end else ""))


def support_ansi() -> bool:
    """
    ## 检查当前终端是否支持 ANSI 颜色
    """
    if not hasattr(sys.stdout, "fileno"):
        # 如果没有文件描述符，则无法检查是否支持 ANSI 颜色
        return False

    try:
        # 检查是否是终端设备
        return os.isatty(sys.stdout.fileno())
    except io.UnsupportedOperation:
        return False


def colored(color: str, text: str, bold: bool = False) -> str:
    """
    ## 为文本添加 ANSI 颜色
    """
    if not support_ansi():
        return text

    # 获取 ANSI 颜色码
    codes = [FOREGROUND_COLORS[color]]

    if bold:
        # 如果需要加粗，则添加 1
        codes.append(1)

    # 返回带有 ANSI 颜色码的文本
    return "\x1b[{}m{}\x1b[0m".format(";".join(map(str, codes)), text)


def call_subprocess(args: list[str]) -> subprocess.CompletedProcess[str, int, bytes, bytes]:
    """
    ## 调用子进程执行命令
    """
    try:
        # 执行命令
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    except subprocess.CalledProcessError as e:
        # 如果执行命令时发生错误，则输出错误信息并退出
        _echo(colored("red", f"\n× 执行指令失败:\n"))
        _echo(colored("red", f"   > Error Code   :   {e.returncode}"))
        _echo(colored("red", f"   > Command      :   {' '.join(args)}"))
        _echo(colored("red", f"   > Stdout       :   {e.stdout}"))
        _echo(colored("red", f"   > Stderr       :   {e.stderr}"))
        sys.exit(e.returncode)


def curl_subprocess(
    args: list[str], task_name: str, error_exit: bool = True, err_echo: bool = True
) -> subprocess.Popen:
    """
    ## 调用子进程执行 curl 命令
    """
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 计算进度条最大长度
    max_length = 80 - len(f"  > 正在执行 {task_name} ") * 2

    # 防止链接中没有任何内容输出, 打印一个假进度条
    _echo(f"\r  > 正在执行 {task_name} [{'-' * max_length}]{0.0}%", end=False)

    for line in process.stderr:
        if match := re.search(r"(\d+(\.\d+)?)%", line):
            # 计算进度
            arrow = ">" * int(round((float(match.group(1)) / 100.0) * max_length))
            spaces = "-" * (max_length - len(arrow))
            bar = f"[{arrow}{spaces}]"
            # 打印进度条
            _echo(f"\r  > 正在执行 {task_name} {bar}{match.group(1)}%", end=False)
    # 等待进程完成
    process.wait()

    if process.returncode == 0:
        # 删除进度条, 打印完成信息
        sys.stdout.write("\r" + " " * 80 + "\r")
        _echo(colored("green", f"√ 任务 {task_name} 完成"))
    elif process.returncode != 0 and err_echo:
        # 删除进度条, 打印错误信息
        sys.stdout.write("\r" + " " * 80 + "\r")
        _echo(colored("red", f"\n× 任务 {task_name} 失败:\n"))
        _echo(colored("red", f"   > Error Code   :   {process.returncode}"))
        _echo(colored("red", f"   > Command      :   {' '.join(args)}"))
        _echo(colored("red", f"   > Stdout       :   {process.stdout.read()}"))
        _echo(colored("red", f"   > Stderr       :   {process.stderr.read()}"))

    # 如果不打印错误信息则清空进度条
    sys.stdout.write("\r" + " " * 80 + "\r")

    # 如果需要退出, 则退出
    if error_exit and process.returncode != 0:
        exit(1)
    else:
        return process


def long_time_subprocess(
    args: list[str], task_name: str, error_exit: bool = True, err_echo: bool = True
) -> subprocess.Popen:
    """
    ## 耗时指令执行, 带一个不确定进度进度条显示

    ## 参数
        - args: list[str] -> 执行的命令
        - task_name: str -> 任务名称
        - error_exit: bool -> 是否在错误时退出
        - err_echo: bool -> 是否打印错误信息

    """
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 计算进度条最大长度
    max_length = 80 - len(f"  > 正在执行 {task_name}  ") * 2

    while True:
        if process.poll() is not None:
            break

        # 向右移动
        for position in range(1, max_length + 1):

            if process.poll() is not None:
                break

            bar = "[" + "-" * (position - 1) + "<NAPCAT>" + "-" * (max_length - position) + "]"
            # 打印进度条
            _echo(f"\r  > 正在执行 {task_name} {bar}", end=False)
            time.sleep(0.2)

        # 向左移动
        for position in range(max_length, 0, -1):

            if process.poll() is not None:
                break

            bar = "[" + "-" * (position - 1) + "<NAPCAT>" + "-" * (max_length - position) + "]"
            # 打印进度条
            _echo(f"\r  > 正在执行 {task_name} {bar}", end=False)
            time.sleep(0.2)

    # 确保进程结束
    process.wait()

    if process.returncode == 0:
        # 删除进度条, 打印完成信息
        sys.stdout.write("\r" + " " * 80 + "\r")
        _echo(colored("green", f"√ 任务 {task_name} 完成"))
    elif process.returncode != 0 and err_echo:
        # 删除进度条, 打印错误信息
        sys.stdout.write("\r" + " " * 80 + "\r")
        _echo(colored("red", f"\n× 任务 {task_name} 失败:\n"))
        _echo(colored("red", f"   > Error Code   :   {process.returncode}"))
        _echo(colored("red", f"   > Command      :   {' '.join(args)}"))
        _echo(colored("red", f"   > Stdout       :   {process.stdout.read()}"))
        _echo(colored("red", f"   > Stderr       :   {process.stderr.read()}"))

    # 如果不打印错误信息则清空进度条
    sys.stdout.write("\r" + " " * 80 + "\r")

    # 如果需要退出, 则退出
    if error_exit and process.returncode != 0:
        exit(1)
    else:
        return process


@dataclasses.dataclass
class QQ:
    """
    ## QQ 相关功能
    """

    qq_download_url: str = None
    qq_remote_version: str = None
    qq_remote_hash: str = None
    qq_local_version: str = None
    package_installer: PackInstaller = None
    package_manager: PackManager = None

    def set_download_qq_url(self) -> None:
        """
        ## 处理 QQ 具体下载链接
        """
        amd64 = {PackInstaller.RPM: DownloadSuffix.AMD64_RPM, PackInstaller.DPKG: DownloadSuffix.AMD64_DEB}
        arm64 = {PackInstaller.RPM: DownloadSuffix.ARM64_RPM, PackInstaller.DPKG: DownloadSuffix.ARM64_DEO}
        arch_map = {"amd64": amd64, "x86_64": amd64, "arm64": arm64, "aarch64": arm64}

        if arch in arch_map and self.package_installer in arch_map[arch]:
            self.qq_download_url += arch_map[arch][self.package_installer].value

    def check_installed(self) -> None:
        """
        ## 检查 QQ 是否需要更新/安装
        """
        if not self.get_local_version():
            # 如果获取不到 本地版本 则直接执行安装 QQ 任务
            self.install()

        elif self.qq_local_version != self.qq_remote_version:
            # 如果本地版本和远程版本不一致, 则执行更新任务
            self.install()

        # 来都来了,更新一下config吧~
        self.update_linuxqq_config()

    def get_local_version(self) -> bool:
        """
        ## 获取本地 QQ 版本
            - 默认安装路径为 /opt/qq

        ## 返回
            - bool: 是否安装 QQ
        """
        try:
            if self.package_installer == PackInstaller.RPM:
                args = ["rpm", "-q", "--queryformat", "%{VERSION}", "linuxqq"]
                self.qq_local_version = subprocess.check_output(args).decode().strip().split("-")[-1]
            elif self.package_installer == PackInstaller.DPKG:
                self.qq_local_version = subprocess.check_output(["dpkg", "-l", "linuxqq"]).decode().strip().split()[-2]
            return True
        except subprocess.CalledProcessError as e:
            # 执行失败则表示没有安装QQ
            return False

    def install(self) -> None:
        """
        ## 下载 QQ
        """
        _echo_logo()  # 输出 NapCat Logo
        _echo(f"正在安装 QQ " f"[{colored('yellow', self.qq_remote_version)}] ")
        _echo("")
        _echo(colored("green", f"√ 检测到系统包管理器: {self.package_manager}"))
        _echo(colored("green", f"√ 检测到软件包安装器: {self.package_installer}"))

        # 设置下载链接
        self.set_download_qq_url()

        # 判断包安装器
        if self.package_installer == PackInstaller.RPM:
            # 执行下载 QQ 任务
            curl_subprocess(["curl", "-L", "-#", self.qq_download_url, "-o", "QQ.rpm"], "下载QQ")

            # 执行安装 QQ 任务
            long_time_subprocess(["yum", "localinstall", "-y", "./QQ.rpm"], "安装QQ")

            # 移除安装包
            if call_subprocess(["rm", "-f", "QQ.rpm"]).returncode:
                _echo(colored("yellow", "× 删除安装包失败, 请手动删除"))

        elif self.package_installer == PackInstaller.DPKG:
            # 执行下载 QQ 任务
            curl_subprocess(["curl", "-L", "-#", self.qq_download_url, "-o", "QQ.deb"], "下载QQ")

            # 执行安装 QQ 以及依赖任务
            long_time_subprocess(["apt-get", "install", "-f", "-y", "./QQ.deb"], "安装QQ")
            long_time_subprocess(["apt-get", "install", "-y", "libnss3"], "安装依赖[libnss3]")
            long_time_subprocess(["apt-get", "install", "-y", "libgbm1"], "安装依赖[libgbm1]")
            long_time_subprocess(["apt-get", "install", "-y", "xvfb"], "安装依赖[xvfb]")

            # 以下操作是为了解决 libasound2 依赖问题
            args = ["apt-get", "install", "-y", "libasound2"]
            if long_time_subprocess(args, "安装依赖[libasound2]", False, False).returncode != 0:
                # 如果安装失败, 则尝试安装 libasound2t64
                args = ["apt-get", "install", "-y", "libasound2t64"]
                long_time_subprocess(args, "安装依赖[libasound2t64]")

            # 移除安装包
            if call_subprocess(["rm", "-f", "QQ.deb"]).returncode:
                _echo(colored("yellow", "× 删除安装包失败, 请手动删除"))

        else:
            _echo(colored("red", "未知的包安装器"))
            sys.exit(1)

    def update_linuxqq_config(self) -> None:
        """
        ## 更新 LinuxQQ 配置
        """
        find_args = ["find", "/home", "-name", "config.json", "-path", "*/.config/QQ/versions/*"]
        configs_list = subprocess.check_output(find_args).decode().split()
        if (config_path := Path("/root/.config/QQ/versions/config.json")).exists():
            configs_list.append(str(config_path))

        for config in configs_list:
            with open(config, "r") as file:
                data = json.load(file)
                data["baseVersion"] = self.qq_remote_version
                data["curVersion"] = self.qq_remote_version
                data["buildId"] = self.qq_remote_hash
            with open(config, "w") as file:
                json.dump(data, file, indent=4)


class ShellInstall:
    """
    ## Shell 方式安装
    """

    def __init__(self):
        # 定义路径
        self.base_path: Path = Path().cwd()

        # QQ 相关路径
        self.qq_install_path: Path = Path("/opt/QQ")
        self.qq_app_path: Path = self.qq_install_path / "resources" / "app"
        self.qq_app_launcher_path: Path = self.qq_install_path / "resources" / "app" / "app_launcher"

        # NapCat 相关路径
        self.napcat_install_path: Path = self.qq_install_path / "NapCat"
        self.napcat_packet_install_path: Path =  self.qq_install_path / "NapCat.Packet"
        self.package_path: Path = self.qq_install_path / "resources" / "app" / "package.json"
        self.napcat_config_path: Path = self.napcat_install_path / "config" / "napcat.json"

        # 拉远程版本
        self.get_remote_version()

        # 定义代理列表
        self.proxy_list = [
            "https://slink.ltd/",
            "https://hub.gitmirror.com/",
            "https://gh.ddlc.top/",
            "https://cors.isteed.cc/",
            "https://ghproxy.cc/",
            "https://github.moeyy.xyz/",
        ]
        # 定义 NapCat 下载链接
        self.napcat_download_url = "https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"
        self.napcat_packet_download_url = "https://github.com/NapNeko/NapCatQQ/releases/latest/download/napcat.packet."

        # 清空终端, 输出 NapCat Logo
        _echo_logo()  # 输出 NapCat Logo
        _echo(
            "正在安装 NapCat [{}] ({})".format(colored("yellow", self.napcat_remote_version), colored("green", "Shell"))
        )
        _echo("")

        # 基础功能检测
        self.detect_package_manager()
        self.detect_package_installer()

    def install_qq(self) -> None:
        """
        ## 安装 QQ
        """
        qq = QQ(
            package_installer=self.package_installer,
            package_manager=self.package_manager,
            qq_download_url=self.qq_download_url,
            qq_remote_version=self.qq_remote_version,
            qq_remote_hash=self.qq_remote_hash,
        )
        qq.check_installed()

    def check_napcat(self) -> None:
        """
        ## 检查是否安装过 NapCat
        """
        _echo_logo()  # 输出 NapCat Logo
        _echo(f"正在安装 NapCat " f"[{colored('yellow', self.napcat_remote_version)}] ")
        _echo("")
        _echo(colored("green", f"√ 检测到系统包管理器: {self.package_manager}"))
        _echo(colored("green", f"√ 检测到软件包安装器: {self.package_installer}"))

        # 检查是否安装过 NapCat
        if not self.napcat_install_path.exists():
            self.download_napcat()
            self.install_napcat()
            return

        if self.napcat_remote_version != self.get_local_version():
            self.download_napcat()
            self.install_napcat()

        else:
            _echo(colored("green", f"√ 检测到 NapCat 已安装且为最新版本[{self.napcat_remote_version}]"))

    def install_napcat(self) -> None:
        """
        ## 安装 NapCat
        """
        # 检查安装目录是否存在
        if not self.napcat_install_path.exists():
            # 如果不存在则创建
            self.napcat_install_path.mkdir()
        else:
            # 如果存在则代表只是更新, 删除除了 config 以外的所有
            for file in self.napcat_install_path.iterdir():
                if file.name != "config":
                    call_subprocess(["rm", "-rf", file])

        # 解压 NapCat
        with zipfile.ZipFile(f"{self.base_path}/NapCat.zip", "r") as zip_ref:
            zip_ref.extractall(str(self.napcat_install_path))
        _echo(colored("green", "√ 解压 NapCat 完成"))

        # 设置NapCat权限
        for item in self.napcat_install_path.rglob("*"):
            item.chmod(0o777)

        # 设置QQ权限
        for item in self.qq_install_path.rglob("*"):
            item.chmod(0o777)

        # 写入 loadNapCat.js
        with open(self.qq_app_path / "loadNapCat.js", "w") as file:
            file.write(f"(async () => {{await import('file:///{self.napcat_install_path}/napcat.mjs');}})();")

        # 移除文件
        Path(self.base_path / "NapCat.zip").unlink()

        # 修改 QQ package.json
        with open(self.package_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # 修改数据
        data["main"] = "./loadNapCat.js"

        # 写入修改后的数据
        with open(self.package_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

    def download_napcat(self) -> None:
        """
        ## 下载 NapCat
        """
        args = [
            "curl",  # 使用 curl 命令
            "-L",  # 跟随重定向
            "-#",  # 显示进度条
            "--connect-timeout",  # 连接超时时间
            "5",  # 5 秒
            self.napcat_download_url,  # 下载链接
            "-o",  # 输出文件
            f"{self.base_path}/NapCat.zip",  # 输出文件路径
        ]
        if curl_subprocess(args, "下载NapCat", False, False).returncode != 0:
            # 如果下载失败, 则尝试使用代理下载
            for proxy in self.proxy_list:
                args[5] = proxy + self.napcat_download_url
                if curl_subprocess(args, f"重试下载NapCat[代理]", False, False).returncode == 0:
                    return
            else:
                _echo(colored("red", "× 下载 NapCat 失败"))
                exit(1)

    def check_packet(self) -> None:
        """
        ## 检查 packet 包
        """
        # 检查路径是否存在, 存在则表示已经安装过, 跳过安装
        if self.napcat_packet_install_path.exists():
            return

        # 创建路径
        self.napcat_packet_install_path.mkdir()

        # 下载 packet 包
        self.download_packet()

        # 安装 packet 包
        self.install_packet()

        # 设置权限
        (self.napcat_packet_install_path / "napcat.packet").chmod(0o777)

    def install_packet(self) -> None:
        """
        ## 安装 packet 包
        """
        # 编辑 NapCat 的默认配置文件
        with open(str(self.napcat_config_path), "r", encoding="utf-8") as file:
            data = json.load(file)

        # 修改数据
        data["packetServer"] = "127.0.0.1:8086"

        # 写入修改后的数据
        with open(str(self.napcat_config_path), "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        # 设置 packet 可执行权限


    def download_packet(self) -> None:
        """
        ## 下载 packet 包
        """
        # 检查系统架构
        if arch == "x86_64" or arch == "amd64":
            self.napcat_packet_download_url += "linux"
        elif arch == "aarch64" or arch == "arm64":
            self.napcat_packet_download_url += "arm"

        # 下载 packet 包
        args = [
            "curl",  # 使用 curl 命令
            "-L",  # 跟随重定向
            "-#",  # 显示进度条
            "--connect-timeout",  # 连接超时时间
            "5",  # 5 秒
            self.napcat_packet_download_url,  # 下载链接
            "-o",  # 输出文件
            f"{self.napcat_packet_install_path}/napcat.packet",  # 输出文件路径
        ]

        if curl_subprocess(args, "下载Packet", False, False).returncode != 0:
            # 如果下载失败, 则尝试使用代理下载
            for proxy in self.proxy_list:
                args[5] = proxy + self.napcat_packet_download_url
                if curl_subprocess(args, f"重试下载Packet[代理]", False, False).returncode == 0:
                    return
            else:
                _echo(colored("red", "× 下载 Packet 失败"))
                exit(1)

    def install_over(self) -> None:
        """
        ## 安装完成
        """
        _echo_logo()  # 输出 NapCat Logo
        _echo("\n")
        _echo(f"{' NapCat 启动方法 '.center(76, '═')}\n")
        _echo("  前台直接启动 请输入 \n    > xvfb-run -a qq --no-sandbox\n")
        _echo("  保持后台运行 请输入 \n    > screen -dmS napcat bash -c xvfb-run -a qq --no-sandbox -q QQ号\n")
        _echo("  PS: 您可以随时使用screen -r napcat来进入后台进程并使用ctrl + a + d离开\n\n")
        _echo(f"{' NapCat.Packet 启动方法 '.center(76, '═')}\n")
        _echo(f"  前台直接启动 请输入 \n    > {self.napcat_packet_install_path}/napcat.packet\n")
        _echo(f"  保持后台运行 请输入 \n    > screen -dmS napcat bash -c {self.napcat_packet_install_path}/napcat.packet\n")
        _echo("\n")
        _echo(f"{' NapCat 安装完成 '.center(76, '═')}")


    def get_local_version(self) -> None:
        """
        ## 获取本地版本
        """
        if not self.napcat_install_path.exists():
            return None

        # 获取本地版本
        with open(self.napcat_install_path / "package.json", "r") as file:
            return "v" + json.load(file)["version"]

    def get_remote_version(self) -> None:
        """
        ## 获取一些列远程版本
        """

        # 获取 NapCat 相关内容
        if (napcat := call_subprocess(["curl", "-s", "https://nclatest.znin.net/"])).returncode != 0:
            _echo(colored("red", "获取 NapCat 版本失败"))
            print(napcat)
            exit(1)

        self.napcat_remote_version = json.loads(napcat.stdout.decode().strip())["tag_name"]

        # 获取 QQ 相关内容
        if (qq := call_subprocess(["curl", "-s", "https://nclatest.znin.net/get_qq_ver"])).returncode != 0:
            _echo(colored("red", "获取 QQ 版本失败"))
            exit(1)

        data = json.loads(qq.stdout.decode().strip())
        self.qq_remote_version = data["linuxVersion"]
        self.qq_remote_hash = data["linuxVerHash"]
        self.qq_download_url = (
            f"https://dldir1.qq.com/qqfile/qq/QQNT/{data['linuxVerHash']}/linuxqq_{self.qq_remote_version}"
        )

    def detect_package_manager(self) -> None:
        """
        ## 检测系统包管理器
        """
        if call_subprocess(["which", "apt-get"]).returncode == 0:
            self.package_manager = PackManager.APT_GET
        elif call_subprocess(["which", "yum"]).returncode == 0:
            self.package_manager = PackManager.YUM
        else:
            _echo(colored("red", "未检测到系统包管理器"))
            sys.exit(1)

        _echo(colored("green", f"√ 检测到系统包管理器: {self.package_manager}"))

    def detect_package_installer(self) -> None:
        """
        ## 检测软件包安装器
        """
        if call_subprocess(["which", "dpkg"]).returncode == 0:
            self.package_installer = PackInstaller.DPKG
        elif call_subprocess(["which", "rpm"]).returncode == 0:
            self.package_installer = PackInstaller.RPM
        else:
            _echo(colored("red", "未检测到包安装器"))
            sys.exit(1)

        _echo(colored("green", f"√ 检测到软件包安装器: {self.package_installer}"))


class DockerInstall:
    """
    ## Docker 方式安装
    """


def select_install_method(stdscr) -> argparse.Namespace:
    """
    选择安装方式
    """
    options = [
        "Shell     - 本地安装 QQ 等所需组件后安装 NapCat 并启动\n",
        "Docker    - 本地安装 Docker 后安装 NapCat 镜像并启动\n",
    ]
    current_row = 0
    # 隐藏光标
    curses.curs_set(0)
    while True:
        stdscr.clear()
        stdscr.addstr(LOGO)
        stdscr.addstr("请手动选择安装方式(使用键盘 ↑ 和 ↓ 选择, 使用 Enter 确认选择)\n\n")

        for idx, option in enumerate(options):
            if idx == current_row:
                stdscr.addstr("   >>> " + option)  # 高亮当前选项
            else:
                stdscr.addstr("       " + option)

        stdscr.refresh()

        key = stdscr.getch()

        # 上下键处理
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(options) - 1:
            current_row += 1
        elif key in [curses.KEY_ENTER, 10, 13]:  # Enter键
            break

    # 根据选择设置 args
    args = argparse.Namespace()
    args.shell = options[current_row] == options[0].replace("   >>> ", "")
    args.docker = options[current_row] == options[1].replace("   >>> ", "")
    return args


def main() -> None:
    """
    ## 程序主入口
    """
    if os.geteuid() != 0:
        # 检查是否以 root 用户运行
        sys.exit("请以 root 用户运行此安装程序!")

    _echo_logo()  # 输出 NapCat Logo
    _echo(colored("green", "欢迎使用 NapCat 安装程序!", bold=True))
    _echo("\n")

    # 解析参数
    parser = argparse.ArgumentParser(description="NapCat 安装脚本")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s", "--shell", action="store_true", help="使用 shell 安装")
    group.add_argument("-d", "--docker", action="store_true", help="使用 Docker 安装")

    if not (args := parser.parse_args()).shell and not args.docker:
        # 当用户没有指定安装方式时, 让用户选择安装方式
        args = curses.wrapper(select_install_method)

    # 开始安装
    if args.shell:
        # 使用 shell 安装
        shell_install = ShellInstall()
        shell_install.install_qq()
        shell_install.check_napcat()
        shell_install.check_packet()
        shell_install.install_over()

    elif args.docker:
        # 使用 Docker 安装
        _echo(colored("green", "开始使用 Docker 安装 NapCat"))


if __name__ == "__main__":
    main()
