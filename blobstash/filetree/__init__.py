import os
from pathlib import Path
from hashlib import blake2b

from blobstash.base.client import Client
from blobstash.base.error import BlobStashError

from requests import HTTPError


class FileTreeError(BlobStashError):
    """Base error for the filetree modue."""


class NodeNotFoundError(FileTreeError):
    """Error returned when a node does not exist."""


def file_hash(path):
    """Return the Blake2b (32 bytes) hash of the file at path."""
    h = blake2b(digest_size=32)
    with open(path, "rb") as f:
        while 1:
            buf = f.read(4096)
            if not buf:
                break
            h.update(buf)

    return h.hexdigest()


class Node:
    """Node represents a node metadata (file or directory)."""

    def __init__(self, name, ref, size, type_, url, metadata, children):
        self.name = name
        self.ref = ref
        self.size = size
        self.type = type_
        self.url = url
        self.metadata = metadata
        self.children = children

    @classmethod
    def from_resp(cls, node):
        node = cls(
            name=node["name"],
            ref=node["ref"],
            size=node.get("size"),
            type_=node["type"],
            url=node.get("url"),
            metadata=node.get("metadata"),
            children=node.get("children"),
        )

        # Recursively parse node's children as Node too
        if node.children:
            children = []
            for child in node.children:
                children.append(Node.from_resp(child))
            node.children = children

        return node

    def is_dir(self):
        return self.type == "dir"

    def is_file(self):
        return self.type == "file"

    def __repr__(self):
        return "blobstash.filetree.Node(name={!r}, ref={!r}, type={!r})".format(
            self.name, self.ref, self.type
        )

    def __hash__(self):
        return hash(self.ref)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return self.ref == other.ref

    def __ne__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return not self.__eq__(other)


class FS:
    """FS represents a file system (a tree of `Node`)."""

    def __init__(self, client, name=None, ref=None, prefix=None):
        self._client = client._client
        self.client = client
        self.name = name
        self.ref = ref
        self.prefix = prefix
        params = {}
        if self.prefix:
            params["prefix"] = self.prefix
        self.params = params

    def __repr__(self):
        return "blobstash.filetree.FS(name={!r})".format(self.name)

    def _path(self, p):
        if self.name:
            return "/api/filetree/fs/fs/" + self.name + p

        return "/api/filetree/fs/ref/" + self.ref + p

    def node(self, path="/"):
        """Return the node stored at path."""
        # TODO(tsileo): add the option to fetch the whole tree in one request, instead of just the childen by default
        try:
            return Node.from_resp(
                self._client.request("GET", self._path(path), params=self.params)
            )
        except HTTPError as error:
            # FIXME(tsileo): remove 500
            if error.response.status_code in [404, 500]:
                raise NodeNotFoundError
            else:
                raise

    def fput_node(self, path, fileobj, content_type=None):
        """Creates a new node at path (file only) with the content of fileobj."""
        return Node.from_resp(
            self._client.request(
                "POST",
                self._path(path),
                files=[("file", (Path(path).name, fileobj, content_type))],
                params=self.params,
            )
        )

    def put_node(self, path, src_path):
        """Creates a new node at path (file only) with the content of the locally stored at src_path."""
        if Path(src_path).is_dir():
            raise FileTreeError("can only put file in a FS")

        try:
            current_node = self.node(path)
            content_hash = current_node.metadata["blake2b-hash"]
            local_hash = file_hash(src_path)
            if local_hash == content_hash:
                return current_node

        except NodeNotFoundError:
            pass

        src = Path(src_path)
        with open(src, "rb") as f:
            return self.fput_node(path, f)

    def download(self, dst_path):
        """Download the file system to locally at dst_path."""
        os.makedirs(dst_path)
        root = self.node()
        self._download(root, "/", dst_path)

    def _download(self, root, root_path, dst_path):
        for child in root.children:
            p = os.path.join(root_path, child.name)
            dst = os.path.join(dst_path, p[1:])
            if child.is_dir():
                new_root = self.node(p)
                os.makedirs(dst)
                self._download(new_root, p, dst_path)
            else:
                # download
                self.client.get_node(child, dst)

    def upload(self, src_path):
        """Creates a new remote filesystem name from the local directory path."""
        p = Path(src_path)
        if p.is_file():
            raise FileTreeError("path must be a dir, not a file")

        self._fs_from_dir_iter(p, base_root=p)

    def _fs_from_dir_iter(self, root, base_root):
        for p in root.iterdir():
            if p.is_file():
                node_path = "/" + str(p.relative_to(base_root))
                # FIXME(tsileo): check the current node (blake2b hash), but handle 404 on node before
                try:
                    current_node = self.node(node_path)
                    content_hash = current_node.metadata["blake2b-hash"]
                    local_hash = file_hash(p.absolute())
                    if local_hash == content_hash:
                        continue

                except NodeNotFoundError:
                    pass
                self.put_node(node_path, p.absolute())
            elif p.is_dir():
                self._fs_from_dir_iter(p, base_root=base_root)


class FileTreeClient:
    """BlobStash FileTree client."""

    def __init__(self, base_url=None, api_key=None, client=None):
        if client:
            self._client = client
            return

        self._client = Client(base_url=base_url, api_key=api_key)

    def fput_node(self, name, fileobj, content_type=None):
        """Upload the fileobj as name, and return the newly created node."""
        return Node.from_resp(
            self._client.request(
                "POST",
                "/api/filetree/upload",
                files=[("file", (name, fileobj, content_type))],
            )
        )

    def put_node(self, path):
        """Uppload the file at the given path, and return the newly created node."""
        name = Path(path).name
        with open(path, "rb") as f:
            return self.fput_node(name, f)

    def fget_node(self, ref_or_node):
        """Returns a file-like object for given node ref.

        It's up to the client to call `close` to release the connection.

        """
        if isinstance(ref_or_node, Node):
            ref = ref_or_node.ref
        else:
            ref = ref_or_node
        return self._client.request(
            "GET", "/api/filetree/file/" + ref, raw=True, stream=True
        ).raw

    def get_node(self, ref_or_node, path):
        """Download the content of the given node at path."""
        with open(path, "wb") as f:
            reader = self.fget_node(ref_or_node)
            try:
                while 1:
                    chunk = reader.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)
            except Exception:  # pragma: no cover
                reader.close()
                raise

    def node(self, ref):
        """Returns the node for the given ref."""
        return Node.from_resp(
            self._client.request("GET", "/api/filetree/node/" + ref)["node"]
        )

    def fs(self, name=None, ref=None, prefix=None):
        """Returns the filesystem for the given name if it exists."""
        return FS(self, name=name, ref=ref, prefix=prefix)

    def __repr__(self):
        return "blobstash.docstore.FileTreeClient(base_url={!r})".format(
            self._client.base_url
        )

    def __str__(self):
        return self.__repr__()
