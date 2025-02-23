# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json

from kombu import Connection
from kombu import Consumer
from kombu import Producer
from kombu import Queue
from kombu.exceptions import TimeoutError
from xivo_test_helpers import bus as bus_helper

from .constants import BUS_QUEUE_NAME
from .constants import BUS_EXCHANGE_XIVO


class BusClient(bus_helper.BusClient):

    def listen_events(self, routing_key, exchange=BUS_EXCHANGE_XIVO):
        with Connection(self._url) as conn:
            queue = Queue(BUS_QUEUE_NAME, exchange=exchange, routing_key=routing_key, channel=conn.channel())
            queue.declare()
            queue.purge()
            self.bus_queue = queue

    def events(self):
        events = []

        def on_event(body, message):
            # events are already decoded, thanks to the content-type
            events.append(body)
            message.ack()

        self._drain_events(on_event=on_event)

        return events

    def _drain_events(self, on_event):
        if not hasattr(self, 'bus_queue'):
            raise Exception('You must listen for events before consuming them')
        with Connection(self._url) as conn:
            with Consumer(conn, self.bus_queue, callbacks=[on_event]):
                try:
                    while True:
                        conn.drain_events(timeout=0.5)
                except TimeoutError:
                    pass

    def send_event(self, event, routing_key):
        with Connection(self._url) as connection:
            producer = Producer(connection, exchange=BUS_EXCHANGE_XIVO, auto_declare=True)
            producer.publish(json.dumps(event), routing_key=routing_key, content_type='application/json')

    def send_ami_newchannel_event(self, channel_id):
        self.send_event({
            'data': {
                'Event': 'Newchannel',
                'Uniqueid': channel_id,
            }
        }, 'ami.Newchannel')

    def send_ami_newstate_event(self, channel_id):
        self.send_event({
            'data': {
                'Event': 'Newstate',
                'Uniqueid': channel_id,
            }
        }, 'ami.Newstate')

    def send_ami_hold_event(self, channel_id):
        self.send_event({
            'data': {
                'Event': 'Hold',
                'Uniqueid': channel_id,
            }
        }, 'ami.Hold')

    def send_ami_unhold_event(self, channel_id):
        self.send_event({
            'data': {
                'Event': 'Unhold',
                'Uniqueid': channel_id,
            }
        }, 'ami.Unhold')

    def send_ami_hangup_event(self, channel_id, base_exten=None, sip_call_id=None):
        self.send_event({
            'data': {
                'Event': 'Hangup',
                'Uniqueid': channel_id,
                'ChannelStateDesc': 'Up',
                'CallerIDName': 'my-caller-id-name',
                'CallerIDNum': 'my-caller-id-num',
                'ConnectedLineName': 'peer-name',
                'ConnectedLineNum': 'peer-num',
                'ChanVariable': {
                    'XIVO_USERUUID': 'my-uuid',
                    'XIVO_BASE_EXTEN': base_exten if base_exten else '*10',
                    'WAZO_SIP_CALL_ID': sip_call_id,
                },
            }
        }, 'ami.Hangup')

    def send_moh_created_event(self, moh_uuid):
        self.send_event({
            'data': {
                'uuid': moh_uuid,
                'name': 'default',
            },
            'name': 'moh_created',
        }, 'config.moh.created')

    def send_moh_deleted_event(self, moh_uuid):
        self.send_event({
            'data': {
                'uuid': moh_uuid,
                'name': 'default',
            },
            'name': 'moh_deleted',
        }, 'config.moh.deleted')

    def send_application_created_event(self, application_uuid, destination=None):
        payload = {
            'data': {
                'uuid': application_uuid,
                'name': 'test-app-name',
                'destination': destination,
                'destination_options': {},
            },
            'name': 'application_created',
        }
        if destination:
            payload['data']['destination_options'] = {
                'type': 'holding',
                'music_on_hold': None,
                'answer': False,
            }
        self.send_event(payload, 'config.applications.created')

    def send_application_edited_event(self, application_uuid, destination=None):
        payload = {
            'data': {
                'uuid': application_uuid,
                'name': 'test-app-name',
                'destination': destination,
                'destination_options': {},
            },
            'name': 'application_edited',
        }
        if destination:
            payload['data']['destination_options'] = {
                'type': 'holding',
                'music_on_hold': None,
                'answer': False,
            }
        self.send_event(payload, 'config.applications.edited')

    def send_application_deleted_event(self, application_uuid):
        payload = {
            'data': {
                'uuid': application_uuid,
                'name': 'test-app-name',
                'destination': None,
                'destination_options': {},
            },
            'name': 'application_deleted',
        }
        self.send_event(payload, 'config.applications.deleted')
