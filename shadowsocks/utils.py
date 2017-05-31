#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, \
    with_statement

import os
import json
import sys
import getopt
import logging
from shadowsocks.common import to_bytes


VERBOSE_LEVEL = 5


def check_python():
    """ 确保 python 版本 2.6+ 或者是 3.3+
    """
    info = sys.version_info
    if info[0] == 2 and not info[1] >= 6:
        print('Python 2.6+ required')
        sys.exit(1)
    elif info[0] == 3 and not info[1] >= 3:
        print('Python 3.3+ required')
        sys.exit(1)
    elif info[0] not in [2, 3]:
        print('Python version not supported')
        sys.exit(1)


def print_shadowsocks():
    """ 打印 shadowsocks 的版本号
    """
    version = ''
    try:
        import pkg_resources
        version = pkg_resources.get_distribution('shadowsocks').version
    except Exception:
        pass
    print('shadowsocks %s' % version)


def find_config():
    """ 返回默认配置文件的路径, 如果没有默认配置, 返回 None

    首先在当前工作目录(current working directory) 查找是否有 config.json;
    接着在本文件(utils.py)的上层目录查找是否有 config.json 文件;

    注意:
    https://github.com/xuelangZF/AnnotatedShadowSocks/issues/1
    __file__ is the pathname of the file from which the module was loaded, if it was loaded from a file.
    __file__ constant is relative to the current working directory
    """
    config_path = 'config.json'
    if os.path.exists(config_path):
        return config_path

    # 注意，join函数中路径字符串前不能带 / .
    # http://stackoverflow.com/questions/918154/relative-paths-in-python
    config_path = os.path.join(os.path.dirname(__file__), '../', 'config.json')
    if os.path.exists(config_path):
        return config_path
    return None


def check_config(config):
    """ 当配置中的参数不合理时, 给出适当的提示信息
    """
    if config.get('local_address', '') in [b'0.0.0.0']:
        logging.warn('warning: local set to listen on 0.0.0.0, it\'s not safe')
    if config.get('server', '') in [b'127.0.0.1', b'localhost']:
        logging.warn('warning: server set to listen on %s:%s, are you sure?' %
                     (config['server'], config['server_port']))
    if (config.get('method', '') or '').lower() == b'table':
        logging.warn('warning: table is not safe; please use a safer cipher, '
                     'like AES-256-CFB')
    if (config.get('method', '') or '').lower() == b'rc4':
        logging.warn('warning: RC4 is not safe; please use a safer cipher, '
                     'like AES-256-CFB')
    if config.get('timeout', 300) < 100:
        logging.warn('warning: your timeout %d seems too short' %
                     int(config.get('timeout')))
    if config.get('timeout', 300) > 600:
        logging.warn('warning: your timeout %d seems too long' %
                     int(config.get('timeout')))
    if config.get('password') in [b'mypassword']:
        logging.error('DON\'T USE DEFAULT PASSWORD! Please change it in your '
                      'config.json!')
        exit(1)


def get_config(is_local):
    """ 获取程序运行的配置信息

    :param is_local: 运行 local 还是 server
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)-s: %(message)s')
    if is_local:
        shortopts = 'hd:s:b:p:k:l:m:c:t:vq'
        longopts = ['help', 'fast-open', 'pid-file=', 'log-file=']
    else:
        shortopts = 'hd:s:p:k:m:c:t:vq'
        longopts = ['help', 'fast-open', 'pid-file=', 'log-file=', 'workers=']
    try:

        # 首先尝试从配置文件读取配置
        config_path = find_config()

        # getopt 是类似于 C 的命令行解析： https://github.com/xuelangZF/AnnotatedShadowSocks/issues/2
        optlist, args = getopt.getopt(sys.argv[1:], shortopts, longopts)

        for key, value in optlist:
            if key == '-c':
                config_path = value

        if config_path:
            logging.info('loading config from %s' % config_path)
            with open(config_path, 'rb') as f:
                try:
                    # 配置文件是 json 格式的，将其加载到字典中（这里字典深度为1）
                    # https://github.com/xuelangZF/AnnotatedShadowSocks/issues/3
                    config = json.loads(f.read().decode('utf8'),
                                        object_hook=_decode_dict)
                except ValueError as e:
                    logging.error('found an error in config.json: %s',
                                  e.message)
                    sys.exit(1)
        else:
            config = {}

        optlist, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
        v_count = 0
        for key, value in optlist:
            if key == '-p':
                config['server_port'] = int(value)
            elif key == '-k':
                config['password'] = to_bytes(value)
            elif key == '-l':
                config['local_port'] = int(value)
            elif key == '-s':
                config['server'] = to_bytes(value)
            elif key == '-m':
                config['method'] = to_bytes(value)
            elif key == '-b':
                config['local_address'] = to_bytes(value)
            elif key == '-v':
                v_count += 1
                # '-vv' turns on more verbose mode
                config['verbose'] = v_count
            elif key == '-t':
                config['timeout'] = int(value)
            elif key == '--fast-open':
                config['fast_open'] = True
            elif key == '--workers':
                config['workers'] = int(value)
            elif key in ('-h', '--help'):
                if is_local:
                    print_local_help()
                else:
                    print_server_help()
                sys.exit(0)
            elif key == '-d':
                config['daemon'] = value
            elif key == '--pid-file':
                config['pid-file'] = value
            elif key == '--log-file':
                config['log-file'] = value
            elif key == '-q':
                v_count -= 1
                config['verbose'] = v_count
    except getopt.GetoptError as e:
        print(e, file=sys.stderr)
        print_help(is_local)
        sys.exit(2)

    if not config:
        logging.error('config not specified')
        print_help(is_local)
        sys.exit(2)

    # 对于没有指定的配置参数，设置默认值
    config['password'] = config.get('password', '')
    config['method'] = config.get('method', 'aes-256-cfb')
    config['port_password'] = config.get('port_password', None)
    config['timeout'] = int(config.get('timeout', 300))
    config['fast_open'] = config.get('fast_open', False)
    config['workers'] = config.get('workers', 1)
    config['pid-file'] = config.get('pid-file', '/var/run/shadowsocks.pid')
    config['log-file'] = config.get('log-file', '/var/log/shadowsocks.log')
    config['workers'] = config.get('workers', 1)
    config['verbose'] = config.get('verbose', False)
    config['local_address'] = config.get('local_address', '127.0.0.1')
    config['local_port'] = config.get('local_port', 1080)

    if is_local:
        if config.get('server', None) is None:
            logging.error('server addr not specified')
            print_local_help()
            sys.exit(2)
    else:
        config['server'] = config.get('server', '0.0.0.0')
    config['server_port'] = config.get('server_port', 8388)

    if is_local and not config.get('password', None):
        logging.error('password not specified')
        print_help(is_local)
        sys.exit(2)

    if not is_local and not config.get('password', None) \
            and not config.get('port_password', None):
        logging.error('password or port_password not specified')
        print_help(is_local)
        sys.exit(2)

    if 'local_port' in config:
        config['local_port'] = int(config['local_port'])

    if 'server_port' in config and type(config['server_port']) != list:
        config['server_port'] = int(config['server_port'])

    logging.getLogger('').handlers = []
    logging.addLevelName(VERBOSE_LEVEL, 'VERBOSE')
    if config['verbose'] >= 2:
        level = VERBOSE_LEVEL
    elif config['verbose'] == 1:
        level = logging.DEBUG
    elif config['verbose'] == -1:
        level = logging.WARN
    elif config['verbose'] <= -2:
        level = logging.ERROR
    else:
        level = logging.INFO
    logging.basicConfig(level=level,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    check_config(config)

    return config


def print_help(is_local):
    """ 打印ss的使用帮助
    """
    if is_local:
        print_local_help()
    else:
        print_server_help()


def print_local_help():
    """ local 客户端命令选项提示, 提供对各个参数的解释。
    """
    print('''usage: sslocal [-h] -s SERVER_ADDR [-p SERVER_PORT]
               [-b LOCAL_ADDR] [-l LOCAL_PORT] -k PASSWORD [-m METHOD]
               [-t TIMEOUT] [-c CONFIG] [--fast-open] [-v] -[d] [-q]
A fast tunnel proxy that helps you bypass firewalls.

You can supply configurations via either config file or command line arguments.

Proxy options:
  -h, --help             show this help message and exit
  -c CONFIG              path to config file
  -s SERVER_ADDR         server address
  -p SERVER_PORT         server port, default: 8388
  -b LOCAL_ADDR          local binding address, default: 127.0.0.1
  -l LOCAL_PORT          local port, default: 1080
  -k PASSWORD            password
  -m METHOD              encryption method, default: aes-256-cfb
  -t TIMEOUT             timeout in seconds, default: 300
  --fast-open            use TCP_FASTOPEN, requires Linux 3.7+

General options:
  -d start/stop/restart  daemon mode
  --pid-file PID_FILE    pid file for daemon mode
  --log-file LOG_FILE    log file for daemon mode
  -v, -vv                verbose mode
  -q, -qq                quiet mode, only show warnings/errors

Online help: <https://github.com/clowwindy/shadowsocks>
''')


def print_server_help():
    """ server 服务器端命令选项提示, 提供对各个参数的解释。
    """
    print('''usage: ssserver [-h] [-s SERVER_ADDR] [-p SERVER_PORT] -k PASSWORD
                -m METHOD [-t TIMEOUT] [-c CONFIG] [--fast-open]
                [--workers WORKERS] [-v] [-d start] [-q]
A fast tunnel proxy that helps you bypass firewalls.

You can supply configurations via either config file or command line arguments.

Proxy options:
  -h, --help             show this help message and exit
  -c CONFIG              path to config file
  -s SERVER_ADDR         server address, default: 0.0.0.0
  -p SERVER_PORT         server port, default: 8388
  -k PASSWORD            password
  -m METHOD              encryption method, default: aes-256-cfb
  -t TIMEOUT             timeout in seconds, default: 300
  --fast-open            use TCP_FASTOPEN, requires Linux 3.7+
  --workers WORKERS      number of workers, available on Unix/Linux

General options:
  -d start/stop/restart  daemon mode
  --pid-file PID_FILE    pid file for daemon mode
  --log-file LOG_FILE    log file for daemon mode
  -v, -vv                verbose mode
  -q, -qq                quiet mode, only show warnings/errors

Online help: <https://github.com/clowwindy/shadowsocks>
''')


def _decode_list(data):
    """ 将 data 中的数据 deserialize 后保存在 list 中

    主要是对 data 中的 unicode string 进行 utf-8 编码
    """
    rv = []
    for item in data:
        if hasattr(item, 'encode'):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    """ 将data（类型为字典）中的数据 deserialize 后保存在 dict 中

    主要是对 data 中的 unicode string 进行 utf-8 编码
    该函数的作用，可以阅读 https://github.com/xuelangZF/AnnotatedShadowSocks/issues/4
    """
    rv = {}
    for key, value in data.items():
        if hasattr(value, 'encode'):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv
