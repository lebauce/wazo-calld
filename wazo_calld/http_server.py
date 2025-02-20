# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os

from cheroot import wsgi
from datetime import timedelta
from flask import Flask, request
from flask_restful import Api
from flask_cors import CORS
from werkzeug.contrib.fixers import ProxyFix
from xivo import http_helpers
from xivo.http_helpers import ReverseProxied

from .http import auth_verifier

VERSION = 1.0

logger = logging.getLogger(__name__)
app = Flask('wazo_calld')
adapter_app = Flask('wazo_calld_adapter')
api = Api(app, prefix='/{}'.format(VERSION))


def log_request_params(response):
    http_helpers.log_request_hide_token(response)
    logger.debug('request data: %s', request.data or '""')
    logger.debug('response body: %s', response.data.strip() if response.data else '""')
    return response


class HTTPServer:

    def __init__(self, global_config):
        self.config = global_config['rest_api']
        http_helpers.add_logger(app, logger)
        http_helpers.add_logger(adapter_app, logger)
        app.before_request(http_helpers.log_before_request)
        app.after_request(log_request_params)
        app.secret_key = os.urandom(24)
        app.permanent_session_lifetime = timedelta(minutes=5)
        app.config['auth'] = global_config['auth']
        adapter_app.after_request(log_request_params)
        adapter_app.permanent_session_lifetime = timedelta(minutes=5)
        auth_verifier.set_config(global_config['auth'])
        self._load_cors()
        self.server = None

    def _load_cors(self):
        cors_config = dict(self.config.get('cors', {}))
        enabled = cors_config.pop('enabled', False)
        if enabled:
            CORS(app, **cors_config)

    def run(self):
        wsgi_app_https = ReverseProxied(ProxyFix(wsgi.WSGIPathInfoDispatcher({'/': app})))

        bind_addr = (self.config['listen'], self.config['port'])
        self.server = wsgi.WSGIServer(bind_addr=bind_addr, wsgi_app=wsgi_app_https)
        self.server.ssl_adapter = http_helpers.ssl_adapter(
            self.config['certificate'],
            self.config['private_key'],
        )
        logger.debug(
            'WSGIServer starting... uid: %s, listen: %s:%s',
            os.getuid(),
            bind_addr[0],
            bind_addr[1],
        )

        for route in http_helpers.list_routes(app):
            logger.debug(route)

        try:
            self.server.start()
        except KeyboardInterrupt:
            logger.warning('Stopping wazo-calld: KeyboardInterrupt')
            self.server.stop()

    def stop(self):
        if self.server:
            self.server.stop()
