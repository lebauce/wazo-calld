# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo import rest_api_helpers

logger = logging.getLogger(__name__)


APIException = rest_api_helpers.APIException


class XiVOAmidError(APIException):

    def __init__(self, xivo_amid_client, error):
        super(XiVOAmidError, self).__init__(
            status_code=503,
            message='xivo-amid request error',
            error_id='xivo-amid-error',
            details={
                'xivo_amid_config': {'host': xivo_amid_client.host,
                                     'port': xivo_amid_client.port,
                                     'timeout': xivo_amid_client.timeout},
                'original_error': str(error),
            }
        )


class ARIUnreachable(Exception):

    def __init__(self, ari_config, original_error=None):
        super(ARIUnreachable, self).__init__('ARI server unreachable... stopping')
        self.ari_config = ari_config
        self.original_error = original_error


class AsteriskARIUnreachable(APIException):

    def __init__(self, asterisk_ari_config, error):
        super(AsteriskARIUnreachable, self).__init__(
            status_code=503,
            message='Asterisk ARI server unreachable',
            error_id='asterisk-ari-unreachable',
            details={
                'asterisk_ari_config': asterisk_ari_config,
                'original_error': str(error),
            }
        )


class AsteriskARIError(APIException):

    def __init__(self, asterisk_ari_config, error):
        super(AsteriskARIError, self).__init__(
            status_code=503,
            message='Asterisk ARI internal error',
            error_id='asterisk-ari-error',
            details={
                'asterisk_ari_config': asterisk_ari_config,
                'original_error': str(error),
            }
        )


class ValidationError(APIException):

    def __init__(self, errors):
        super(ValidationError, self).__init__(
            status_code=400,
            message='Sent data is invalid',
            error_id='invalid-data',
            details=errors
        )


class TokenWithUserUUIDRequiredError(APIException):

    def __init__(self):
        super(TokenWithUserUUIDRequiredError, self).__init__(
            status_code=400,
            message='A valid token with a user UUID is required',
            error_id='token-with-user-uuid-required',
        )


class UserHasNoLine(APIException):

    def __init__(self, user_uuid):
        super(UserHasNoLine, self).__init__(
            status_code=400,
            message='Invalid user: user has no line',
            error_id='user-has-no-line',
            details={
                'user_uuid': user_uuid
            }
        )


class InvalidUserUUID(APIException):

    def __init__(self, user_uuid):
        super(InvalidUserUUID, self).__init__(
            status_code=400,
            message='Invalid user: not found',
            error_id='invalid-user',
            details={
                'user_uuid': user_uuid
            }
        )


class XiVOConfdUnreachable(APIException):

    def __init__(self, xivo_confd_client, error):
        super(XiVOConfdUnreachable, self).__init__(
            status_code=503,
            message='xivo-confd server unreachable',
            error_id='xivo-confd-unreachable',
            details={
                'xivo_confd_config': {'host': xivo_confd_client.host,
                                      'port': xivo_confd_client.port,
                                      'timeout': xivo_confd_client.timeout},
                'original_error': str(error),
            }
        )


class UserPermissionDenied(APIException):

    def __init__(self, user_uuid, details):
        details = dict(details)
        details['user'] = user_uuid
        super(UserPermissionDenied, self).__init__(
            status_code=403,
            message='User does not have permission to handle objects of other users',
            error_id='user-permission-denied',
            details=details
        )
