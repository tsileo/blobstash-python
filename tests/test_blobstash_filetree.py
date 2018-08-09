import io
import os
import shutil
import subprocess

import pytest

from blobstash.base.test_utils import BlobStash
from blobstash.filetree import FileTreeClient, FileTreeError


def test_filetree_node_fileobj():
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = FileTreeClient(api_key="123")

        # Try to upload a basic fileobj
        expected = b"Hello world"
        node = client.fput_node("hello.txt", io.BytesIO(expected))

        # Get it back and compare it
        f = client.fget_node(node)
        out = f.read()
        assert out == expected
        assert node.name == "hello.txt"
        assert node.size == len(expected)
        assert node.type == "file"
    finally:
        b.shutdown()
        b.cleanup()


def test_filetree_node_file():
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = FileTreeClient(api_key="123")
        # Upload the README from the souce tree
        node = client.put_node("README.md")
        assert node.name == "README.md"
        assert node.type == "file"

        # Ensure we can get it back
        node2 = client.node(node.ref)
        assert node == node2

        # Try downloading the file back using the `Node` object
        try:
            client.get_node(node, "README2.md")
            assert subprocess.check_call(["diff", "README.md", "README2.md"]) == 0
        finally:
            os.unlink("README2.md")

        # Now using the string reference
        try:
            client.get_node(node.ref, "README3.md")
            assert subprocess.check_call(["diff", "README.md", "README3.md"]) == 0
        finally:
            os.unlink("README3.md")

    finally:
        b.shutdown()
        b.cleanup()


def test_filetree_fs_upload_download():
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = FileTreeClient(api_key="123")
        for i in ["1", "2"]:
            fs = client.fs("source_code")

            if i == "1":
                with pytest.raises(FileTreeError):
                    # Can't upload a file as a dir
                    fs.upload("README.md")

            fs.upload("blobstash")
            try:
                fs.download("blobstash" + i)
                assert (
                    subprocess.check_call(["diff", "blobstash" + i, "blobstash"]) == 0
                )
            finally:
                shutil.rmtree("blobstash" + i)
    finally:
        b.shutdown()
        b.cleanup()


def test_filetree_fs():
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = FileTreeClient(api_key="123")

        fs = client.fs("test_fs")

        # Ensure we can't put a dir
        with pytest.raises(FileTreeError):
            fs.put_node("/path", "docs")

        readme = fs.put_node("/README.md", "README.md")

        root = fs.node()
        assert len(root.children) == 1
        readme2 = root.children[0]
        assert readme2.name == "README.md"
        assert readme2 == readme

        # Put it twice
        license = fs.put_node("/path/to/LICENSE", "LICENSE")
        license = fs.put_node("/path/to/LICENSE", "LICENSE")
        root = fs.node()
        assert len(root.children) == 2

        subdir = fs.node("/path")
        assert len(subdir.children) == 1
        assert subdir.children[0].name == "to"
        assert subdir.children[0].type == "dir"

        subdir2 = fs.node("/path/to")
        assert len(subdir2.children) == 1
        assert subdir2.children[0] == license

        license2 = fs.node("/path/to/LICENSE")
        assert license2 == license

    finally:
        b.shutdown()
        b.cleanup()
