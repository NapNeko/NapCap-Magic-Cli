# -*- coding: utf-8 -*-
import argparse
import io
import json
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

# 检查 Python 版本是否符合要求, 如果低于版本 3.8 则退出
if sys.version_info < (3, 9):
    sys.exit("安装 NapCat 需要 Python 3.9 或更高版本")

# 获取当前系统信息
arch = platform.machine()

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
}

# 定义终端输出 NapCat Install Logo
LOGO = '''\n\n
    ███╗   ██╗  █████╗  ██████╗   ██████╗  █████╗  ████████╗
    ████╗  ██║ ██╔══██╗ ██╔══██╗ ██╔════╝ ██╔══██╗ ╚══██╔══╝
    ██╔██╗ ██║ ███████║ ██████╔╝ ██║      ███████║    ██║   
    ██║╚██╗██║ ██╔══██║ ██╔═══╝  ██║      ██╔══██║    ██║   
    ██║ ╚████║ ██║  ██║ ██║      ╚██████╗ ██║  ██║    ██║   
    ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚═╝       ╚═════╝ ╚═╝  ╚═╝    ╚═╝   \n\n\n
'''


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


def _call_subprocess(args: list[str]) -> subprocess.CompletedProcess[str, int, bytes, bytes]:
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


class ShellInstall:
    """
    ## Shell 方式安装
    """

    def __init__(self):
        # 定义路径
        self.base_path = Path().cwd()

        # 拉版本
        self.ger_remote_version()

        # 清空终端, 输出 NapCat Logo
        os.system('clear')
        _echo(colored("pink", LOGO, bold=True))  # 输出 NapCat Logo
        _echo("正在安装 NapCat [{}] ({})".format(
            colored('yellow', self.napcat_remote_version), colored("green", "Shell")
        ))
        _echo("\n")

        # 基础功能检测
        self.detect_package_manager()
        self.detect_package_installer()

    def install_qq(self) -> None:
        """
        ## 安装 QQ
        """
        ...

    def ger_remote_version(self):
        """
        ## 获取一些列远程版本
        """

        # 获取 NapCat 相关内容
        if (napcat := _call_subprocess(['curl', '-s', 'https://nclatest.znin.net/'])).returncode != 0:
            _echo(colored('red', "获取 NapCat 版本失败"))
            print(napcat)
            exit(1)

        self.napcat_remote_version = json.loads(napcat.stdout.decode().strip())["tag_name"]

        # 获取 QQ 相关内容
        if (qq := _call_subprocess(['curl', '-s', 'https://nclatest.znin.net/get_qq_ver'])).returncode != 0:
            _echo(colored('red', "获取 QQ 版本失败"))
            exit(1)

        data = json.loads(qq.stdout.decode().strip())
        self.qq_remote_version = data["linuxVersion"]
        self.qq_download_url = \
            f"https://dldir1.qq.com/qqfile/qq/QQNT/{data['linuxVerHash']}/linuxqq_{self.qq_remote_version}"

    def detect_package_manager(self) -> None:
        """
        ## 检测系统包管理器
        """
        if _call_subprocess(['which', 'apt-get']).returncode == 0:
            self.package_manager = 'apt'
        elif _call_subprocess(['which', 'yum']).returncode == 0:
            self.package_manager = 'yum'
        else:
            _echo(colored('red', "未检测到系统包管理器"))
            sys.exit(1)

        _echo(colored('green', f"√ 检测到系统包管理器: {self.package_manager}"))

    def detect_package_installer(self) -> None:
        """
        ## 检测软件包安装器
        """
        if _call_subprocess(['which', 'dpkg']).returncode == 0:
            self.package_installer = 'apt-get'
        elif _call_subprocess(['which', 'rpm']).returncode == 0:
            self.package_installer = 'yum'
        else:
            _echo(colored('red', "未检测到包安装器"))
            sys.exit(1)

        _echo(colored('green', f"√ 检测到软件包安装器: {self.package_installer}"))


class DockerInstall:
    """
    ## Docker 方式安装
    """


def main() -> None:
    """
    ## 程序主入口
    """

    # 清空终端, 输出 NapCat Logo
    os.system('clear')
    _echo(colored("pink", LOGO, bold=True))  # 输出 NapCat Logo
    _echo(colored("green", "欢迎使用 NapCat 安装程序!", bold=True))
    _echo("\n")

    # 解析参数
    parser = argparse.ArgumentParser(description="NapCat 安装脚本")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-s', '--shell', action='store_true', help='使用 shell 安装')
    group.add_argument('-d', '--docker', action='store_true', help='使用 Docker 安装')

    if not (args := parser.parse_args()).shell and not args.docker:
        # # 当用户没有指定安装方式时, 让用户选择安装方式
        _echo(colored('yellow', "未检测到安装方式参数传入, 请手动选择安装方式\n"))
        _echo("{:<10}  适用于全平台\n".format("  > shell"))
        _echo("{:<10}  适用于 Linux 系统\n".format("  > docker"))

        if input("请选择安装方式(shell/docker)[shell]: ").strip().lower() == 'docker':
            args.docker = True
        else:
            args.shell = True

        _echo("\n")

    # 开始安装
    if args.shell:
        # 使用 shell 安装
        shell_install = ShellInstall()
    elif args.docker:
        # 使用 Docker 安装
        _echo(colored('green', "开始使用 Docker 安装 NapCat"))


if __name__ == '__main__':
    main()
