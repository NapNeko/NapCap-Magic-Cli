# -*- coding: utf-8 -*-
import io
import os
import platform
import subprocess
import sys
import argparse
import curses
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
LOGO = '''\n\n\n
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


def chose_install_manner(stdscr) -> None:
    """
    ## 选择安装方式
    """
    # 清空屏幕
    stdscr.clear()

    # 定义选项
    options = [
        "shell: 适用于全平台",
        "docker: 适用于 Linux 系统"
    ]

    current_selection = 0  # 当前选择的索引

    while True:
        # 显示选项
        for idx, option in enumerate(options):
            if idx == current_selection:
                # 高亮显示当前选择
                stdscr.addstr(idx, 0, option, curses.A_REVERSE)
            else:
                stdscr.addstr(idx, 0, option)

        # 刷新屏幕
        stdscr.refresh()

        # 获取用户输入
        key = stdscr.getch()

        if key == curses.KEY_UP and current_selection > 0:
            current_selection -= 1
        elif key == curses.KEY_DOWN and current_selection < len(options) - 1:
            current_selection += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            # 用户按下回车键
            break

    # 清空屏幕，显示选择结果
    stdscr.clear()
    stdscr.addstr(0, 0, f"您选择了: {options[current_selection]}")
    stdscr.refresh()
    stdscr.getch()  # 等待用户按键以结束程序


def main() -> None:
    """
    ## 程序主入口
    """

    # 清空终端, 输出 NapCat Logo
    os.system('clear')
    _echo(colored("pink", LOGO))  # 输出 NapCat Logo
    _echo(colored("green", "欢迎使用 NapCat 安装程序!"))
    _echo("\n")

    # 解析参数
    parser = argparse.ArgumentParser(description="NapCat 安装脚本")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-s', '--shell', action='store_true', help='使用 shell 安装')
    group.add_argument('-d', '--docker', action='store_true', help='使用 Docker 安装')

    if not (args := parser.parse_args()).shell and not args.docker:
        # # 当用户没有指定安装方式时, 让用户选择安装方式
        # _echo(colored('yellow', "未检测到安装方式参数传入, 请手动选择安装方式\n"))
        # _echo("{:<10}  适用于全平台\n".format("  > shell"))
        # _echo("{:<10}  适用于 Linux 系统\n".format("  > docker"))
        #
        # if input("请选择安装方式(shell/docker)[shell]: ").strip().lower() or 'shell' == 'docker':
        #     args.docker = True
        # else:
        #     args.shell = True
        #
        # _echo("\n")

        # 启动 curses 应用
        curses.wrapper(chose_install_manner)

    # 开始安装
    if args.shell:
        # 使用 shell 安装
        _echo(colored('green', "开始使用 shell 安装 NapCat"))
    elif args.docker:
        # 使用 Docker 安装
        _echo(colored('green', "开始使用 Docker 安装 NapCat"))


if __name__ == '__main__':
    main()
