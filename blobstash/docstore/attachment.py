"""Attachment utils."""
from blobstash.filetree import FileTreeClient

_FILETREE_POINTER_FMT = '@filetree/ref:{}'


class Attachment:
    """An attachment represents a file stored in FileTree and tied to the document via a pointer."""

    def __init__(self, pointer, node):
        self.pointer = pointer
        self.node = node

    def __repr__(self):
        return 'blobstash.docstore.attachment.Attachment(pointer={!r}, node={!r})'.format(self.pointer, self.node)


def add_attachment(client, name, fileobj, content_type=None):
    """Create a new attachment (i.e. upload the file to FileTree, and return a pointer object."""
    node = FileTreeClient(client=client).fput_node(name, fileobj, content_type)
    pointer = _FILETREE_POINTER_FMT.format(node.ref)
    return Attachment(pointer, node)


def get_attachment(client, attachment):
    """Returns a fileobj (that needs to be closed) with the content off the attachment."""
    return FileTreeClient(client=client).fget_node(attachment.node)
