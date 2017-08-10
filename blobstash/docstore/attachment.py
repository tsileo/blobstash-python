"""Attachment utils."""
from blobstash.filetree import FileTreeClient

_FILETREE_POINTER_FMT = '@filetree/ref:{}'


class Attachment:
    def __init__(self, pointer, data):
        self.pointer_type = 'filetree/ref'
        self.pointer = pointer
        self.data = data

    def __repr__(self):
        return 'Attachment(pointer={!r}, data={!r})'.format(self.pointer, self.data)


def add_attachment(client, name, fileobj, content_type=None):
    node = FileTreeClient(client=client).fput_node(name, fileobj, content_type)
    pointer = _FILETREE_POINTER_FMT.format(node.ref)
    return Attachment(pointer, node)
