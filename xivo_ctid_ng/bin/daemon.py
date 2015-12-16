# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


import logging
import sys

from xivo.daemonize import pidfile_context
from xivo.user_rights import change_user
from xivo import xivo_logging
from xivo_ctid_ng.controller import Controller
from xivo_ctid_ng.config import load as load_config

logger = logging.getLogger(__name__)


def main(argv):
    config = load_config(argv)

    if config['user']:
        change_user(config['user'])

    xivo_logging.setup_logging(config['log_filename'], config['foreground'], config['debug'], config['log_level'])
    xivo_logging.silence_loggers(['amqp', 'Flask-Cors', 'kombu', 'swaggerpy', 'urllib3'], logging.WARNING)

    controller = Controller(config)

    with pidfile_context(config['pid_filename'], config['foreground']):
        controller.run()


if __name__ == '__main__':
    main(sys.argv[1:])
