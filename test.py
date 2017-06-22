import unittest
from unittest import mock

import transfer

from state import StateMonitor


class TestMemoryReaderTestCase(unittest.TestCase):
    def setUp(self):
        self.patcher = mock.patch('transfer.open', mock.mock_open(read_data=b'\x01\x02\x03'), create=True)
        self.patcher.start()
        self.reader = transfer.SimpleMemoryFileReader('/somewhere/in/the/middle')

    def tearDown(self):
        self.patcher.stop()

    def test_reading_single_byte(self):
        assert self.reader.read_bytes(1) == b'\x01'
        assert self.reader.read_bytes(1) == b'\x02'
        assert self.reader.read_bytes(1) == b'\x03'

    def test_reading_multiple_bytes(self):
        assert self.reader.read_bytes(2) == b'\x01\x02'
        assert self.reader.read_bytes(1) == b'\x03'


class TestStateMonitorTestCase(unittest.TestCase):
    def setUp(self):
        prepare_mock = mock.Mock()
        stream_mock = mock.Mock()
        self.prepare_mock, self.stream_mock = prepare_mock, stream_mock

        class TestingClass:
            state = 'PREPARE'

            @StateMonitor.dispatch(
                ('PREPARE', 'handle_prepare'),
                ('STREAM', 'handle_stream')
            )
            def data_received(self, data):
                pass

            def handle_prepare(self, data):
                prepare_mock()
                return 'handle_prepare'

            def handle_stream(self, data):
                stream_mock()
                return 'handle_stream'

        self.testing_class = TestingClass

    def test_dispatching_to_prepare(self):
        self.instance = self.testing_class()
        self.instance.data_received('some_data')
        self.prepare_mock.assert_called_once()

    def test_dispatching_to_stream(self):
        self.instance = self.testing_class()
        self.instance.state = 'STREAM'
        self.instance.data_received('some_data')
        self.stream_mock.assert_called_once()
