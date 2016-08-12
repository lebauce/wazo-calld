# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import os
import time

from hamcrest import assert_that
from hamcrest import has_item
from hamcrest import matches_regexp
from hamcrest import not_
from xivo_test_helpers import until

from .test_api.ari_ import MockChannel
from .test_api.base import IntegrationTest
from .test_api.constants import BUS_EXCHANGE_COLLECTD
from .test_api.constants import STASIS_APP_NAME
from .test_api.constants import STASIS_APP_INSTANCE_NAME
from .test_api.ctid_ng import new_call_id


class TestCollectd(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestCollectd, cls).setUpClass()
        time.sleep(4)  # wait for xivo-ctid-ng to connect to the bus

    def setUp(self):
        super(TestCollectd, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_when_new_channel_then_stat_channel_start(self):
        channel_id = 'channel-id'
        self.bus.listen_events(routing_key='collectd.channels', exchange=BUS_EXCHANGE_COLLECTD)

        self.bus.send_ami_newchannel_event(channel_id=channel_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/channels-global/counter-created .* N:1'
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_channel_ends_then_stat_channel_ended(self):
        channel_id = 'channel-id'
        self.bus.listen_events(routing_key='collectd.channels', exchange=BUS_EXCHANGE_COLLECTD)

        self.bus.send_ami_hangup_event(channel_id=channel_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/channels-global/counter-ended .* N:1'
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_new_stasis_channel_then_stat_call_start(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)

        self.stasis.event_stasis_start(channel_id=call_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-start .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_then_stat_call_end(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-end .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_then_stat_call_duration(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id,
                                            creation_time='2016-02-01T15:00:00.000-0500',
                                            timestamp='2016-02-01T16:00:00.000-0500')

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/gauge-duration .* N:3600'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_given_connected_when_stasis_channel_destroyed_then_do_not_stat_abandoned_call(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id,
                                            connected_number='another-number')

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-abandoned .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), not_(has_item(matches_regexp(expected_message))))

        until.assert_(assert_function, tries=3)

    def test_given_not_connected_when_stasis_channel_destroyed_then_stat_abandoned_call(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-abandoned .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_connect_then_stat_connect(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)

        self.stasis.event_stasis_start(channel_id=call_id, stasis_args=['dialed_from', 'another-channel'])

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-connect .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), not_(has_item(matches_regexp(expected_message))))

        until.assert_(assert_function, tries=3)


class TestCollectdCtidNgRestart(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestCollectdCtidNgRestart, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_ctid_ng_restarts_during_call_when_stasis_channel_destroyed_then_stat_call_end(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)
        self.stasis.event_stasis_start(channel_id=call_id)

        self.restart_service('ctid-ng')
        until.true(self.ari.websockets, tries=5)  # wait for xivo-ctid-ng to come back up
        self.stasis.event_channel_destroyed(channel_id=call_id)

        def assert_ctid_ng_sent_end_call_stat():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-end .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_ctid_ng_sent_end_call_stat, tries=5)


class TestCollectdRabbitMQRestart(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestCollectdRabbitMQRestart, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_rabbitmq_restarts_during_call_when_stasis_channel_destroyed_then_stat_call_end(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.stasis.event_stasis_start(channel_id=call_id)

        self.restart_service('rabbitmq')
        until.true(self.bus.is_up, tries=int(os.environ.get('INTEGRATION_TEST_TIMEOUT', 30)))  # wait for rabbitmq to come back up

        self.bus.listen_events(routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD)
        self.stasis.event_channel_destroyed(channel_id=call_id)

        def assert_ctid_ng_sent_end_call_stat():
            expected_message = 'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-end .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_ctid_ng_sent_end_call_stat, tries=5)
