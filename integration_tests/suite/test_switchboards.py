# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from ari.exceptions import ARINotInStasis
from hamcrest import (
    assert_that,
    contains,
    contains_string,
    contains_inanyorder,
    empty,
    equal_to,
    has_entry,
    has_entries,
    has_item,
    has_items,
    is_not,
    starts_with,
)
from operator import attrgetter
from xivo_test_helpers import until

from .helpers.auth import MockUserToken
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.constants import VALID_TOKEN, VALID_TENANT
from .helpers.confd import (
    MockSwitchboard,
    MockLine,
    MockUser,
)
from .helpers.hamcrest_ import HamcrestARIChannel

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
STASIS_APP = 'callcontrol'
STASIS_APP_INSTANCE = 'switchboard'
STASIS_APP_QUEUE = 'switchboard_queue'
UUID_NOT_FOUND = '99999999-9999-9999-9999-999999999999'
CALL_ID_NOT_FOUND = '99999999.99'
TENANT_UUID_NOT_FOUND = '99999999-9999-9999-9999-999999999991'


class TestSwitchboards(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)
        self.confd.reset()

    def channel_is_in_stasis(self, channel_id):
        try:
            self.ari.channels.setChannelVar(channelId=channel_id, variable='TEST_STASIS', value='')
            return True
        except ARINotInStasis:
            return False

    def channels_are_bridged(self, caller, callee):
        try:
            next(bridge for bridge in self.ari.bridges.list()
                 if (caller.id in bridge.json['channels'] and
                     callee.id in bridge.json['channels'] and
                     bridge.json['bridge_type'] == 'mixing'))
            return True
        except StopIteration:
            return False

    def latest_chantest_channel(self):
        chan_test_channels = [channel for channel in self.ari.channels.list()
                              if channel.json['name'].startswith('Test/')]
        return max(chan_test_channels, key=attrgetter('id'))


class TestSwitchboardCallsQueued(TestSwitchboards):

    def test_given_no_confd_when_list_queued_calls_then_503(self):
        with self.confd_stopped():
            result = self.calld.get_switchboard_queued_calls_result(UUID_NOT_FOUND, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_switchboard_then_404(self):
        result = self.calld.get_switchboard_queued_calls_result(UUID_NOT_FOUND, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_no_bridges_then_return_empty_list(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))

        calls = self.calld.switchboard_queued_calls(switchboard_uuid)

        assert_that(calls, has_entry('items', empty()))

    def test_given_switchboard_in_other_tenant_then_401(self):
        switchboard_uuid = 'my-switchboard-uuid'
        switchboard = MockSwitchboard(uuid=switchboard_uuid)
        self.confd.set_switchboards(switchboard)

        result = self.calld.get_switchboard_queued_calls_result(
            switchboard_uuid,
            token=VALID_TOKEN,
            tenant_uuid=TENANT_UUID_NOT_FOUND,
        )

        assert_that(result.status_code, equal_to(401))

    def test_given_one_call_hungup_then_return_empty_list(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(self.channel_is_in_stasis, new_channel.id, tries=2)
        new_channel.hangup()

        calls = self.calld.switchboard_queued_calls(switchboard_uuid)

        assert_that(calls, has_entry('items', empty()))

    def test_given_two_call_in_queue_then_list_two_calls(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel_1 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        new_channel_2 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        def assert_function():
            calls = self.calld.switchboard_queued_calls(switchboard_uuid)
            assert_that(
                calls,
                has_entry('items', contains_inanyorder(
                    has_entry('id', new_channel_1.id),
                    has_entry('id', new_channel_2.id),
                ))
            )

        until.assert_(assert_function, tries=3)

    def test_given_two_call_in_queue_and_one_hangup_then_list_one_call(self):

        def calls_are_queued(*expected_call_ids):
            calls = self.calld.switchboard_queued_calls(switchboard_uuid)
            actual_call_ids = [call['id'] for call in calls['items']]
            assert_that(actual_call_ids, contains_inanyorder(*expected_call_ids))

        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel_1 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        new_channel_2 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        until.assert_(calls_are_queued, new_channel_1.id, new_channel_2.id, tries=3)

        new_channel_1.hangup()

        until.assert_(calls_are_queued, new_channel_2.id, tries=3)

    def test_given_no_calls_when_new_queued_call_then_bus_event(self):
        switchboard_uuid = 'my-switchboard-uuid'
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        bus_events = self.bus.accumulator(routing_key)
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        def event_received():
            assert_that(
                bus_events.accumulate(),
                contains(has_entries({
                    'name': 'switchboard_queued_calls_updated',
                    'data': has_entries({
                        'switchboard_uuid': switchboard_uuid,
                        'items': contains(has_entry(
                            'id', new_channel.id,
                        )),
                    })
                }))
            )

        until.assert_(event_received, tries=3)

    def test_given_one_call_queued_when_hangup_then_bus_event(self):
        switchboard_uuid = 'my-switchboard-uuid'
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        bus_events = self.bus.accumulator(routing_key)
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        until.true(bus_events.accumulate, tries=3)

        new_channel.hangup()

        def event_received():
            assert_that(
                bus_events.accumulate(),
                contains(
                    has_entries({
                        'name': 'switchboard_queued_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': is_not(empty()),
                        })
                    }),
                    has_entries({
                        'name': 'switchboard_queued_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': empty(),
                        })
                    })
                )
            )

        until.assert_(event_received, tries=3)

    def test_given_calld_stopped_and_queued_is_hung_up_when_calld_starts_then_bus_event(self):
        switchboard_uuid = 'my-switchboard-uuid'
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        bus_events = self.bus.accumulator(routing_key)
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        until.true(bus_events.accumulate, tries=3)

        with self._calld_stopped():
            new_channel.hangup()

        def event_received():
            assert_that(
                bus_events.accumulate(),
                has_items(
                    has_entries({
                        'name': 'switchboard_queued_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': is_not(empty()),
                        })
                    }),
                    has_entries({
                        'name': 'switchboard_queued_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': empty(),
                        })
                    })
                )
            )
        until.assert_(event_received, tries=3)

    @unittest.skip
    def test_given_one_call_queued_answered_held_when_unhold_then_no_queued_calls_updated_bus_event(self):
        '''
        To be implemented when holding calls will be possible, testing that
        WAZO_SWITCHBOARD_QUEUE is reset correctly when leaving the queue
        '''
        pass


class TestSwitchboardCallsQueuedAnswer(TestSwitchboards):

    def test_given_no_confd_when_answer_queued_call_then_503(self):
        with self.confd_stopped():
            result = self.calld.put_switchboard_queued_call_answer_result(
                UUID_NOT_FOUND, CALL_ID_NOT_FOUND, token=VALID_TOKEN
            )

        assert_that(result.status_code, equal_to(503))

    def test_given_no_switchboard_when_answer_then_404(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = UUID_NOT_FOUND
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        line = MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test')
        self.confd.set_lines(line)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id

        result = self.calld.put_switchboard_queued_call_answer_result(switchboard_uuid, queued_call_id, token)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('switchboard'))

    def test_given_no_queued_call_when_answer_then_404(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))

        result = self.calld.put_switchboard_queued_call_answer_result(switchboard_uuid, CALL_ID_NOT_FOUND, token)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('call'))

    def test_given_token_with_no_user_when_answer_then_400(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        bus_events = self.bus.accumulator('switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)

        result = self.calld.put_switchboard_queued_call_answer_result(switchboard_uuid, queued_call_id, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('user'))

    def test_given_operator_has_no_line_when_answer_then_400(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)

        result = self.calld.put_switchboard_queued_call_answer_result(switchboard_uuid, queued_call_id, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('line'))

    def test_given_one_queued_call_and_one_operator_when_answer_then_operator_is_bridged(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)

        result = self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)

        operator_channel = self.ari.channels.get(channelId=result['call_id'])
        until.true(self.channels_are_bridged, operator_channel, new_channel, tries=3)

    def test_given_one_queued_call_and_one_operator_when_answer_then_bus_event(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        first_line_id = 1
        second_line_id = 2
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[first_line_id, second_line_id]))
        self.confd.set_lines(
            MockLine(id=first_line_id, name='switchboard-first-line/autoanswer', protocol='test'),
            MockLine(id=second_line_id, name='switchboard-second-line/autoanswer', protocol='test')
        )
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        routing_key = 'switchboards.{uuid}.calls.queued.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(queued_bus_events.accumulate, tries=3)

        result = self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)

        def answered_event_received():
            assert_that(answered_bus_events.accumulate(), has_item(has_entries({
                'name': 'switchboard_queued_call_answered',
                'data': has_entries({
                    'switchboard_uuid': switchboard_uuid,
                    'operator_call_id': result['call_id'],
                    'queued_call_id': queued_call_id
                })
            })))

        until.assert_(answered_event_received, tries=3)

        # Verify main line is used
        channels = self.ari.channels.list()
        assert_that(len(channels), equal_to(2))
        channel_answer = [c for c in channels if c.id != queued_call_id][0]
        assert_that(
            channel_answer.json.get('name'),
            starts_with('Test/switchboard-first-line')
        )

    def test_given_one_queued_call_and_one_operator_when_answer_with_second_line_then_bus_event(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        first_line_id = 1
        second_line_id = 2
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[first_line_id, second_line_id]))
        self.confd.set_lines(
            MockLine(id=first_line_id, name='switchboard-first-line/autoanswer', protocol='test'),
            MockLine(id=second_line_id, name='switchboard-second-line/autoanswer', protocol='test')
        )
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        routing_key = 'switchboards.{uuid}.calls.queued.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(queued_bus_events.accumulate, tries=3)

        result = self.calld.switchboard_answer_queued_call(switchboard_uuid,
                                                           queued_call_id,
                                                           token, second_line_id)

        def answered_event_received():
            assert_that(answered_bus_events.accumulate(), has_item(has_entries({
                'name': 'switchboard_queued_call_answered',
                'data': has_entries({
                    'switchboard_uuid': switchboard_uuid,
                    'operator_call_id': result['call_id'],
                    'queued_call_id': queued_call_id
                })
            })))

        until.assert_(answered_event_received, tries=3)

        # Verify second line is used
        channels = self.ari.channels.list()
        assert_that(len(channels), equal_to(2))
        channel_answer = [c for c in channels if c.id != queued_call_id][0]
        assert_that(
            channel_answer.json.get('name'),
            starts_with('Test/switchboard-second-line')
        )

    def test_given_one_queued_call_and_one_operator_when_answer_then_caller_id_is_correct_before_and_after_phone_answer(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        queued_caller_id = '"câller" <1234>'.encode('utf-8')
        operator_caller_id = '"ôperator" <9876>'.encode('utf-8')
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
            callerId=queued_caller_id,
        )
        until.true(queued_bus_events.accumulate, tries=3)
        queued_call_id = new_channel.id
        result = self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)
        operator_call_id = result['call_id']
        operator_channel = self.ari.channels.get(channelId=operator_call_id)
        operator_channel.setChannelVar(variable='XIVO_ORIGINAL_CALLER_ID', value=operator_caller_id, bypassStasis=True)

        assert_that(
            operator_channel.json,
            has_entry('caller', has_entries({'name': 'câller', 'number': '1234'}))
        )

        routing_key = 'switchboards.{uuid}.calls.queued.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        self.chan_test.answer_channel(operator_channel.id)
        until.true(answered_bus_events.accumulate, tries=3)

        operator_channel = self.ari.channels.get(channelId=operator_call_id)
        assert_that(
            operator_channel.json,
            has_entry('caller', has_entries({'name': 'ôperator', 'number': '9876'}))
        )

    def test_given_operator_is_answering_a_hungup_channel_when_answer_then_operator_is_hungup(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)
        result = self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)
        operator_channel_id = result['call_id']
        new_channel.hangup()

        self.chan_test.answer_channel(operator_channel_id)

        def operator_is_hungup():
            assert_that(operator_channel_id, self.c.is_hungup())

        until.assert_(operator_is_hungup, tries=3)


class TestSwitchboardHoldCall(TestSwitchboards):

    def test_given_no_confd_when_hold_call_then_503(self):
        with self.confd_stopped():
            result = self.calld.put_switchboard_held_call_result(
                UUID_NOT_FOUND, CALL_ID_NOT_FOUND, token=VALID_TOKEN
            )

        assert_that(result.status_code, equal_to(503))

    def test_given_no_switchboard_when_hold_call_then_404(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(queued_bus_events.accumulate, tries=3)

        result = self.calld.put_switchboard_held_call_result(
            UUID_NOT_FOUND,
            queued_call_id,
            token=VALID_TOKEN
        )

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('switchboard'))

    def test_given_no_call_when_hold_call_then_404(self):
        switchboard_uuid = 'my-switchboard-uuid'
        call_id = CALL_ID_NOT_FOUND
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))

        result = self.calld.put_switchboard_held_call_result(
            switchboard_uuid,
            call_id,
            token=VALID_TOKEN
        )

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('call'))

    def test_given_operator_is_talking_when_hold_call_then_held_call_is_up_and_operator_is_hungup(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        routing_key = 'switchboards.{uuid}.calls.queued.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(queued_bus_events.accumulate, tries=3)
        result = self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)
        operator_channel_id = result['call_id']
        until.true(answered_bus_events.accumulate, tries=3)

        self.calld.switchboard_hold_call(switchboard_uuid, queued_call_id)

        def operator_is_hungup():
            assert_that(operator_channel_id, self.c.is_hungup())

        until.assert_(operator_is_hungup, tries=3)
        assert_that(queued_call_id, self.c.is_talking())

    def test_given_operator_is_talking_when_hold_call_then_bus_event(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.queued.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)
        until.true(answered_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)

        self.calld.switchboard_hold_call(switchboard_uuid, queued_call_id)

        def event_received():
            assert_that(
                held_bus_events.accumulate(),
                contains(has_entries({
                    'name': 'switchboard_held_calls_updated',
                    'data': has_entries({
                        'switchboard_uuid': switchboard_uuid,
                        'items': contains(
                            has_entry('id', queued_call_id)
                        ),
                    })
                }))
            )

        until.assert_(event_received, tries=3)

    def test_hold_same_call_twice(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        queued_call_id = new_channel.id
        until.true(queued_bus_events.accumulate, tries=3)

        routing_key = 'switchboards.{uuid}.calls.queued.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)
        until.true(answered_bus_events.accumulate, tries=3)

        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, queued_call_id)
        until.true(held_bus_events.accumulate, tries=3)

        routing_key = 'switchboards.{uuid}.calls.queued.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_answer_queued_call(switchboard_uuid, queued_call_id, token)
        until.true(answered_bus_events.accumulate, tries=3)

        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, queued_call_id)
        until.true(held_bus_events.accumulate, tries=3)


class TestSwitchboardCallsHeld(TestSwitchboards):

    def test_given_no_confd_when_list_held_calls_then_503(self):
        with self.confd_stopped():
            result = self.calld.get_switchboard_held_calls_result(UUID_NOT_FOUND, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_switchboard_then_404(self):
        result = self.calld.get_switchboard_held_calls_result(UUID_NOT_FOUND, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_switchboard_in_other_tenant_then_401(self):
        switchboard_uuid = 'my-switchboard-uuid'
        switchboard = MockSwitchboard(uuid=switchboard_uuid)
        self.confd.set_switchboards(switchboard)

        result = self.calld.get_switchboard_held_calls_result(
            switchboard_uuid,
            token=VALID_TOKEN,
            tenant_uuid=TENANT_UUID_NOT_FOUND,
        )

        assert_that(result.status_code, equal_to(401))

    def test_given_no_bridges_then_return_empty_list(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))

        calls = self.calld.switchboard_held_calls(switchboard_uuid)

        assert_that(calls, has_entry('items', empty()))

    def test_given_one_call_hungup_then_return_empty_list(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        new_channel.hangup()

        calls = self.calld.switchboard_held_calls(switchboard_uuid)

        assert_that(calls, has_entry('items', empty()))

    def test_given_two_calls_held_then_list_two_calls(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel_1 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        new_channel_2 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel_1.id)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel_2.id)

        def assert_function():
            calls = self.calld.switchboard_held_calls(switchboard_uuid)
            assert_that(
                calls,
                has_entry('items', contains_inanyorder(
                    has_entry('id', new_channel_1.id),
                    has_entry('id', new_channel_2.id),
                ))
            )

        until.assert_(assert_function, tries=3)

    def test_given_two_calls_held_and_one_hangup_then_list_one_call(self):

        def calls_are_held(*expected_call_ids):
            calls = self.calld.switchboard_held_calls(switchboard_uuid)
            actual_call_ids = [call['id'] for call in calls['items']]
            assert_that(actual_call_ids, contains_inanyorder(*expected_call_ids))

        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel_1 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        new_channel_2 = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel_1.id)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel_2.id)

        until.assert_(calls_are_held, new_channel_1.id, new_channel_2.id, tries=3)

        new_channel_1.hangup()

        until.assert_(calls_are_held, new_channel_2.id, tries=3)

    def test_given_one_call_held_when_hangup_then_bus_event(self):
        switchboard_uuid = 'my-switchboard-uuid'
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)

        new_channel.hangup()

        def event_received():
            assert_that(
                held_bus_events.accumulate(),
                contains(
                    has_entries({
                        'name': 'switchboard_held_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': is_not(empty())
                        })
                    }),
                    has_entries({
                        'name': 'switchboard_held_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': empty()
                        })
                    })
                )
            )

        until.assert_(event_received, tries=3)

    def test_given_calld_stopped_and_held_is_hung_up_when_calld_starts_then_bus_event(self):
        switchboard_uuid = 'my-switchboard-uuid'
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)

        with self._calld_stopped():
            new_channel.hangup()

        def event_received():
            assert_that(
                held_bus_events.accumulate(),
                has_items(
                    has_entries({
                        'name': 'switchboard_held_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': is_not(empty())
                        })
                    }),
                    has_entries({
                        'name': 'switchboard_held_calls_updated',
                        'data': has_entries({
                            'switchboard_uuid': switchboard_uuid,
                            'items': empty()
                        })
                    })
                )
            )

        until.assert_(event_received, tries=3)


class TestSwitchboardCallsHeldAnswer(TestSwitchboards):

    def test_given_no_confd_when_answer_held_call_then_503(self):
        with self.confd_stopped():
            result = self.calld.put_switchboard_held_call_answer_result(
                UUID_NOT_FOUND, CALL_ID_NOT_FOUND, token=VALID_TOKEN
            )

        assert_that(result.status_code, equal_to(503))

    def test_given_no_switchboard_when_answer_then_404(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        switchboard_uuid = UUID_NOT_FOUND
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )

        result = self.calld.put_switchboard_held_call_answer_result(switchboard_uuid, new_channel.id, token)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('switchboard'))

    def test_given_no_held_call_when_answer_then_404(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))

        result = self.calld.put_switchboard_held_call_answer_result(switchboard_uuid, CALL_ID_NOT_FOUND, token)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('call'))

    def test_given_token_with_no_user_when_answer_then_400(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)
        held_call_id = new_channel.id

        result = self.calld.put_switchboard_held_call_answer_result(switchboard_uuid, held_call_id, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('user'))

    def test_given_operator_has_no_line_when_answer_then_400(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)
        held_call_id = new_channel.id

        result = self.calld.put_switchboard_held_call_answer_result(switchboard_uuid, held_call_id, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('line'))

    def test_given_one_held_call_and_one_operator_when_answer_then_operator_is_bridged(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)
        held_call_id = new_channel.id

        result = self.calld.switchboard_answer_held_call(switchboard_uuid, held_call_id, token)

        operator_channel = self.ari.channels.get(channelId=result['call_id'])
        until.true(self.channels_are_bridged, operator_channel, new_channel, tries=3)

    def test_given_one_held_call_and_one_operator_when_answer_then_bus_event(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        first_line_id = 1
        second_line_id = 2
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[first_line_id, second_line_id]))
        self.confd.set_lines(
            MockLine(id=first_line_id, name='switchboard-first-line/autoanswer', protocol='test'),
            MockLine(id=second_line_id, name='switchboard-second-line/autoanswer', protocol='test')
        )
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        held_bus_events = self.bus.accumulator('switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid))
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)
        held_call_id = new_channel.id
        routing_key = 'switchboards.{uuid}.calls.held.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)

        result = self.calld.switchboard_answer_held_call(switchboard_uuid, held_call_id, token)

        def answered_event_received():
            assert_that(answered_bus_events.accumulate(), has_item(has_entries({
                'name': 'switchboard_held_call_answered',
                'data': has_entries({
                    'switchboard_uuid': switchboard_uuid,
                    'operator_call_id': result['call_id'],
                    'held_call_id': held_call_id
                })
            })))

        until.assert_(answered_event_received, tries=3)

        # Verify main line is used
        channels = self.ari.channels.list()
        assert_that(len(channels), equal_to(2))
        channel_answer = [c for c in channels if c.id != held_call_id][0]
        assert_that(
            channel_answer.json.get('name'),
            starts_with('Test/switchboard-first-line')
        )

    def test_given_one_held_call_and_one_operator_when_answer_with_second_line_then_bus_event(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        first_line_id = 1
        second_line_id = 2
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[first_line_id, second_line_id]))
        self.confd.set_lines(
            MockLine(id=first_line_id, name='switchboard-first-line/autoanswer', protocol='test'),
            MockLine(id=second_line_id, name='switchboard-second-line/autoanswer', protocol='test')
        )
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        held_bus_events = self.bus.accumulator('switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid))
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)
        held_call_id = new_channel.id
        routing_key = 'switchboards.{uuid}.calls.held.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)

        result = self.calld.switchboard_answer_held_call(switchboard_uuid,
                                                         held_call_id, token,
                                                         second_line_id)

        def answered_event_received():
            assert_that(answered_bus_events.accumulate(), has_item(has_entries({
                'name': 'switchboard_held_call_answered',
                'data': has_entries({
                    'switchboard_uuid': switchboard_uuid,
                    'operator_call_id': result['call_id'],
                    'held_call_id': held_call_id,
                })
            })))

        until.assert_(answered_event_received, tries=3)

        # Verify second line is used
        channels = self.ari.channels.list()
        assert_that(len(channels), equal_to(2))
        channel_answer = [c for c in channels if c.id != held_call_id][0]
        assert_that(
            channel_answer.json.get('name'),
            starts_with('Test/switchboard-second-line')
        )

    def test_given_one_held_call_and_one_operator_when_answer_then_caller_id_is_correct_before_and_after_phone_answer(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        held_caller_id = '"câller" <1234>'.encode('utf-8')
        operator_caller_id = '"ôperator" <9876>'.encode('utf-8')
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
            callerId=held_caller_id,
        )
        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)
        held_call_id = new_channel.id
        result = self.calld.switchboard_answer_held_call(switchboard_uuid, held_call_id, token)
        operator_call_id = result['call_id']
        operator_channel = self.ari.channels.get(channelId=operator_call_id)
        operator_channel.setChannelVar(
            variable='XIVO_ORIGINAL_CALLER_ID',
            value=operator_caller_id,
            bypassStasis=True,
        )

        assert_that(
            operator_channel.json,
            has_entry('caller', has_entries({'name': 'câller', 'number': '1234'}))
        )

        routing_key = 'switchboards.{uuid}.calls.held.*.answer.updated'.format(uuid=switchboard_uuid)
        answered_bus_events = self.bus.accumulator(routing_key)
        self.chan_test.answer_channel(operator_channel.id)
        until.true(answered_bus_events.accumulate, tries=3)

        operator_channel = self.ari.channels.get(channelId=operator_call_id)
        assert_that(
            operator_channel.json,
            has_entry('caller', has_entries({'name': 'ôperator', 'number': '9876'}))
        )

    def test_given_operator_is_answering_a_hungup_channel_when_answer_then_operator_is_hungup(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid=VALID_TENANT))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator', protocol='test'))
        routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        queued_bus_events = self.bus.accumulator(routing_key)
        new_channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app=STASIS_APP,
            appArgs=[STASIS_APP_INSTANCE, STASIS_APP_QUEUE, VALID_TENANT, switchboard_uuid],
        )
        until.true(queued_bus_events.accumulate, tries=3)
        routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        held_bus_events = self.bus.accumulator(routing_key)
        self.calld.switchboard_hold_call(switchboard_uuid, new_channel.id)
        until.true(held_bus_events.accumulate, tries=3)
        held_call_id = new_channel.id
        result = self.calld.switchboard_answer_held_call(switchboard_uuid, held_call_id, token)
        operator_channel_id = result['call_id']
        new_channel.hangup()

        self.chan_test.answer_channel(operator_channel_id)

        def operator_is_hungup():
            assert_that(operator_channel_id, self.c.is_hungup())

        until.assert_(operator_is_hungup, tries=3)
