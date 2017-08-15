"""Attachment utils."""
from uuid import uuid4
from pathlib import Path

from blobstash.filetree import FileTreeClient
from blobstash.docstore.error import DocStoreError

_FILETREE_POINTER_FMT = '@filetree/ref:{}'
_FILETREE_ATTACHMENT_FS_PREFIX = '_filetree:docstore'


class Attachment:
    """An attachment represents a file stored in FileTree and tied to the document via a pointer."""

    def __init__(self, pointer, node):
        self.pointer = pointer
        self.node = node

    def __repr__(self):
        return 'blobstash.docstore.attachment.Attachment(pointer={!r}, node={!r})'.format(self.pointer, self.node)


def add_attachment(client, path):
    """Creates a new attachment (i.e. upload the file or directory to FileTree), and returns a pointer object."""
    p = Path(path)
    if p.is_file():
        with open(p.absolute(), 'rb') as fileobj:
            node = FileTreeClient(client=client).fput_node(p.name, fileobj, content_type=None)
    else:
        fs = FileTreeClient(client=client).fs(uuid4().hex, prefix=_FILETREE_ATTACHMENT_FS_PREFIX)
        fs.upload(path)
        node = fs.node()

    pointer = _FILETREE_POINTER_FMT.format(node.ref)
    return Attachment(pointer, node)


def fadd_attachment(client, name, fileobj, content_type=None):
    """Creates a new attachment from the fileobj content with name as filename and returns a pointer object."""
    node = FileTreeClient(client=client).fput_node(name, fileobj, content_type)
    pointer = _FILETREE_POINTER_FMT.format(node.ref)
    return Attachment(pointer, node)


def fget_attachment(client, attachment):
    """Returns a fileobj (that needs to be closed) with the content off the attachment."""
    node = attachment.node
    if node.is_dir():
        raise DocStoreError('cannot get a fileobj for a directory, please use get_attachment instead')

    return FileTreeClient(client=client).fget_node(node)


def get_attachment(client, attachment, path):
    node = attachment.node
    if node.is_file():
        FileTreeClient(client=client).get_node(node, path)
        return

    FileTreeClient(client=client).fs(ref=node.ref, prefix=_FILETREE_ATTACHMENT_FS_PREFIX).download(path)
