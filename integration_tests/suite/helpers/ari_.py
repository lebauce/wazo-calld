# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests


class ARIClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return 'http://{host}:{port}/{path}'.format(host=self.host,
                                                    port=self.port,
                                                    path='/'.join(parts))

    def set_applications(self, *mock_applications):
        url = self.url('_set_response')
        body = {'response': 'applications',
                'content': {application.name(): application.to_dict() for application in mock_applications}}
        requests.post(url, json=body)

    def set_channels(self, *mock_channels):
        url = self.url('_set_response')
        body = {'response': 'channels',
                'content': {channel.id_(): channel.to_dict() for channel in mock_channels}}
        requests.post(url, json=body)

    def set_bridges(self, *mock_bridges):
        url = self.url('_set_response')
        body = {'response': 'bridges',
                'content': {bridge.id_(): bridge.to_dict() for bridge in mock_bridges}}
        requests.post(url, json=body)

    def set_originates(self, *mock_channels):
        url = self.url('_set_response')
        body = {'response': 'originates',
                'content': [channel.to_dict() for channel in mock_channels]}
        requests.post(url, json=body)

    def set_channel_variable(self, variables):
        url = self.url('_set_response')
        body = {'response': 'channel_variables',
                'content': variables}
        requests.post(url, json=body)

    def set_global_variables(self, variables):
        url = self.url('_set_response')
        body = {'response': 'global_variables',
                'content': variables}
        requests.post(url, json=body)

    def reset(self):
        url = self.url('_reset')
        requests.post(url)

    def requests(self):
        url = self.url('_requests')
        return requests.get(url).json()

    def websockets(self):
        url = self.url('_websockets')
        return requests.get(url).json()


class MockApplication:

    def __init__(self, name, channels=None):
        self._name = name
        self._channels = channels or []

    def name(self):
        return self._name

    def to_dict(self):
        return {
            'name': self._name,
            'channel_ids': self._channels,
        }


class MockChannel:

    def __init__(self,
                 id,
                 state='Ringing',
                 creation_time='2015-01-01T00:00:00.0-0500',
                 caller_id_name='someone',
                 caller_id_number='somewhere',
                 connected_line_name='someone else',
                 connected_line_number='somewhere else',
                 name='something'):
        self._id = id
        self._state = state
        self._creation_time = creation_time
        self._caller_id_name = caller_id_name
        self._caller_id_number = caller_id_number
        self._connected_line_name = connected_line_name
        self._connected_line_number = connected_line_number
        self._name = name

    def id_(self):
        return self._id

    def to_dict(self):
        return {
            'id': self._id,
            'state': self._state,
            'creationtime': self._creation_time,
            'caller': {
                'name': self._caller_id_name,
                'number': self._caller_id_number
            },
            'connected': {
                'name': self._connected_line_name,
                'number': self._connected_line_number
            },
            'name': self._name,
            'dialplan': {
                'context': None,
                'exten': None,
                'priority': None,
                'app_name': None,
                'app_data': None,
            },
        }


class MockBridge:

    def __init__(self, id, channels=None):
        self._id = id
        self._channels = channels or []

    def id_(self):
        return self._id

    def to_dict(self):
        return {
            'id': self._id,
            'channels': self._channels
        }
