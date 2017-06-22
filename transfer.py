import asyncio
import json
import abc
import os
import click

from state import StateMonitor

from tqdm import tqdm


KiB = 2**10


class FileReader(metaclass=abc.ABCMeta):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file = open(file_path, 'rb')

    @abc.abstractmethod
    def read_bytes(self, n):
        pass

    def get_info(self):
        return {
            'name': os.path.split(self.file_path)[1],
            'size': os.stat(self.file_path).st_size
        }


class SimpleMemoryFileReader(FileReader):
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.data = self.file.read()
        self.pointer = 0

    def read_bytes(self, n):
        result = self.data[self.pointer: self.pointer+n]

        self.pointer += n
        return result


class FileWriter(metaclass=abc.ABCMeta):
    def __init__(self, file_path: str):
        self.file = open(file_path, 'wb')

    @abc.abstractmethod
    def write(self, data):
        pass


class SimpleFileWriter(FileWriter):

    def write(self, data):
        self.file.write(data)
        return len(data)


class RedProtocol(asyncio.Protocol):
    READERS = {
        'memoryfile': SimpleMemoryFileReader
    }

    def __init__(self, path: str, reader_class='memoryfile'):
        self.loop = asyncio.get_event_loop()
        self.reader = self.READERS[reader_class](path)

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        request = json.loads(data)
        if request['type'] == 'info':
            response = json.dumps({'type': 'info', 'data': self.reader.get_info()}).encode('utf-8')
            self.transport.write(response)
        if request['type'] == 'data':
            nbytes = request['bytes']
            self.transport.write(self.reader.read_bytes(nbytes))


class RedClient(asyncio.Protocol):
    def __init__(self, path):
        self.loop = asyncio.get_event_loop()
        self.path = path
        self.state = 'PREPARATION'
        self.file_data = {}
        self.writer = None
        self.transport = None
        self.received_bytes = 0
        self.to_receive = None
        self.progress = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport.write(json.dumps({'type': 'info'}).encode('utf-8'))

    def _ask_for_data(self, nbytes):
        self.transport.write(json.dumps({
            'type': 'data',
            'bytes': nbytes
        }).encode('utf-8'))

    @StateMonitor.dispatch(
        ('PREPARE', 'handle_prepare'),
        ('STREAM', 'handle_stream'),
    )
    def data_received(self, data):
        pass

    def handle_prepare(self, data):
        data = json.loads(data)
        if data['type'] == 'info':
            self.file_data = data['data']
            self.to_receive = self.file_data['size']
            self.progress = tqdm(total=self.to_receive)
            download_path = os.path.join(self.path, self.file_data['name'])
            self.writer = SimpleFileWriter(download_path)
            self.state = 'STREAM'
            self._ask_for_data(10*KiB)

    def handle_stream(self, data):
        nbytes = self.writer.write(data)
        self.received_bytes += nbytes
        self.progress.update(nbytes)
        if nbytes:
            self._ask_for_data(10*KiB)
        if self.received_bytes == self.to_receive:
            self.loop.stop()
            print('Download completed')


@click.group()
@click.pass_context
def cli(ctx):
    pass


@cli.command()
@click.option('--path', type=click.Path(exists=True), required=True, help="Path to file to be served")
@click.option('--ip', type=click.STRING, default='0.0.0.0', help='Your ip address you\'re streaming from, defaults to 0.0.0.0')
@click.pass_context
def serve(ctx, path, ip):
    loop = asyncio.get_event_loop()

    coro = loop.create_server(lambda: RedProtocol(path), ip, 8888)
    server = loop.run_until_complete(coro)

    print('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()


@cli.command()
@click.option('--ip', type=click.STRING, required=True, help='IP Address of server to download from')
@click.option('--path', type=click.Path(exists=True, dir_okay=True), required=True, help="Path to file to be served")
@click.pass_context
def download(ctx, path, ip):
    loop = asyncio.get_event_loop()
    downloader_coro = loop.create_connection(lambda: RedClient(path), ip, 8888)
    loop.run_until_complete(downloader_coro)
    loop.run_forever()
    loop.close()

if __name__ == '__main__':
    cli(obj={})
