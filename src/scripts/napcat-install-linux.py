# -*- coding: utf-8 -*-
# 标准库导入
import io
import os
import re
import sys
import json
import time
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
LOGO = """\n\n
    ███╗   ██╗  █████╗  ██████╗   ██████╗  █████╗  ████████╗
    ████╗  ██║ ██╔══██╗ ██╔══██╗ ██╔════╝ ██╔══██╗ ╚══██╔══╝
    ██╔██╗ ██║ ███████║ ██████╔╝ ██║      ███████║    ██║   
    ██║╚██╗██║ ██╔══██║ ██╔═══╝  ██║      ██╔══██║    ██║   
    ██║ ╚████║ ██║  ██║ ██║      ╚██████╗ ██║  ██║    ██║   
    ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚═╝       ╚═════╝ ╚═╝  ╚═╝    ╚═╝   \n\n\n
"""


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
        _echo(colored("red", f"执行以下命令时引发错误{args}"))
        sys.exit(e.returncode)


def curl_subprocess(args: list[str], task_name: str) -> None:
    """
    ## 调用子进程执行 curl 命令
    """
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    for line in process.stderr:
        if match := re.search(r"(\d+(\.\d+)?)%", line):
            # 计算进度
            arrow = ">" * int(round((float(match.group(1)) / 100.0) * 60) - 1)
            spaces = "-" * (60 - len(arrow) - 3)
            bar = f"[{arrow}{spaces}]"
            # 打印进度条
            _echo(f"\r  > 正在下载 {task_name} {bar}{match.group(1)}%", end=False)
    # 等待进程完成
    process.wait()

    if process.returncode == 0:
        # 删除进度条, 打印完成信息
        sys.stdout.write("\r" + " " * 100 + "\r")
        _echo(colored("green", f"√ {task_name} 下载完成"))
    else:
        # 删除进度条, 打印错误信息
        _echo(colored("red", f"\n下载 {task_name} 失败:\n"))
        _echo(colored("red", f"   > Error Code   :   {process.returncode}"))
        _echo(colored("red", f"   > Download Url :   {args[3]}"))
        exit(1)


def long_time_subprocess(args: list[str], task_name: str, error_exit: bool = True) -> subprocess.Popen:
    """
    ## 耗时指令执行, 带一个不确定进度进度条显示
    """
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    while process.poll():
        # 向右移动
        for position in range(1, 42 + 1):
            bar = "[" + "-" * (position - 1) + "<< < N A P C A T > >>" + "-" * (42 - position) + "]"
            # 打印进度条
            _echo(f"\r  > 正在执行 {task_name} {bar}", end=False)
            time.sleep(0.2)

        # 向左移动
        for position in range(42, 0, -1):
            bar = "[" + "-" * (position - 1) + "<< < N A P C A T > >>" + "-" * (42 - position) + "]"
            # 打印进度条
            _echo(f"\r  > 正在执行 {task_name} {bar}", end=False)
            time.sleep(0.2)

    # 确保进程结束
    process.wait()

    if process.returncode == 0:
        # 删除进度条, 打印完成信息
        sys.stdout.write("\r" + " " * 100 + "\r")
        _echo(colored("green", f"√ 任务 {task_name} 完成"))
    else:
        # 删除进度条, 打印错误信息
        _echo(colored("red", f"\n任务 {task_name} 失败:\n"))
        _echo(colored("red", f"   > Error Code   :   {process.returncode}"))
        _echo(colored("red", f"   > Command      :   {' '.join(args)}"))
        _echo(colored("red", f"   > Stdout       :   {process.stdout.read()}"))
        _echo(colored("red", f"   > Stderr       :   {process.stderr.read()}"))

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
        # TODO 待实现

    def get_local_version(self) -> None:
        """
        ## 获取本地 QQ 版本
            - 默认安装路径为 /opt/qq
        """
        # TODO 待实现

    def install(self) -> None:
        """
        ## 下载 QQ
        """
        # 清空终端, 输出 NapCat Logo
        os.system("clear")
        _echo(colored("pink", LOGO, bold=True))  # 输出 NapCat Logo
        _echo(f"正在安装 QQ " f"[{colored('yellow', self.qq_remote_version)}] ")
        _echo("\n")
        _echo(colored("green", f"√ 检测到系统包管理器: {self.package_manager}"))
        _echo(colored("green", f"√ 检测到软件包安装器: {self.package_installer}"))

        # 设置下载链接
        self.set_download_qq_url()

        # 判断包安装器
        if self.package_installer == PackInstaller.RPM:
            # 执行下载 QQ 任务
            curl_subprocess(["curl", "-L", "-#", self.qq_download_url, "-o", "QQ.rpm"], "QQ")

            # 执行安装 QQ 任务
            long_time_subprocess(["yum", "localinstall", "-y", "./QQ.rpm"], "安装QQ")

            # 移除安装包
            if call_subprocess(["rm", "-f", "QQ.rpm"]).returncode:
                _echo(colored("yellow", "× 删除安装包失败, 请手动删除"))

        elif self.package_installer == PackInstaller.DPKG:
            # 执行下载 QQ 任务
            curl_subprocess(["curl", "-L", "-#", self.qq_download_url, "-o", "QQ.deb"], "QQ")

            # 执行安装 QQ 以及依赖任务
            long_time_subprocess(["apt-get", "install", "-f", "-y", "./QQ.deb"], "安装QQ")
            long_time_subprocess(["apt-get", "install", "-y", "libnss3"], "安装依赖[libnss3]")
            long_time_subprocess(["apt-get", "install", "-y", "libgbm1"], "安装依赖[libgbm1]")

            # 以下操作是为了解决 libasound2 依赖问题
            args = ["apt-get", "install", "-y", "libasound2"]
            if long_time_subprocess(args, "安装依赖[libasound2]", False).returncode != 0:
                # 如果安装失败, 则尝试安装 libasound2t64
                args = ["apt-get", "install", "-y", "libasound2t64"]
                long_time_subprocess(args, "安装依赖[libasound2t64]")

            # 移除安装包
            if call_subprocess(["rm", "-f", "QQ.deb"]).returncode:
                _echo(colored("yellow", "× 删除安装包失败, 请手动删除"))

        else:
            _echo(colored("red", "未知的包安装器"))
            sys.exit(1)


class ShellInstall:
    """
    ## Shell 方式安装
    """

    def __init__(self):
        # 定义路径
        self.base_path = Path().cwd()

        # 拉远程版本
        self.get_remote_version()

        # 清空终端, 输出 NapCat Logo
        os.system("clear")
        _echo(colored("pink", LOGO, bold=True))  # 输出 NapCat Logo
        _echo(
            "正在安装 NapCat [{}] ({})".format(colored("yellow", self.napcat_remote_version), colored("green", "Shell"))
        )
        _echo("\n")

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
        )
        qq.install()

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


def main() -> None:
    """
    ## 程序主入口
    """
    if os.geteuid() != 0:
        # 检查是否以 root 用户运行
        sys.exit("请以 root 用户运行此安装程序!")

    # 清空终端, 输出 NapCat Logo
    os.system("clear")
    _echo(colored("pink", LOGO, bold=True))  # 输出 NapCat Logo
    _echo(colored("green", "欢迎使用 NapCat 安装程序!", bold=True))
    _echo("\n")

    # 解析参数
    parser = argparse.ArgumentParser(description="NapCat 安装脚本")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s", "--shell", action="store_true", help="使用 shell 安装")
    group.add_argument("-d", "--docker", action="store_true", help="使用 Docker 安装")

    if not (args := parser.parse_args()).shell and not args.docker:
        # 当用户没有指定安装方式时, 让用户选择安装方式
        _echo(colored("yellow", "未检测到安装方式参数传入, 请手动选择安装方式\n"))
        _echo("  > shell")
        _echo("  > docker")
        _echo("")

        if input("请选择安装方式(shell/docker)[shell]: ").strip().lower() == "docker":
            args.docker = True
        else:
            args.shell = True

        _echo("\n")

    # 开始安装
    if args.shell:
        # 使用 shell 安装
        shell_install = ShellInstall()
        shell_install.install_qq()
    elif args.docker:
        # 使用 Docker 安装
        _echo(colored("green", "开始使用 Docker 安装 NapCat"))


if __name__ == "__main__":
    main()
