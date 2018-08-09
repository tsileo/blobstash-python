"""Utils for unit tests, also used for BlobStash (and related projects) integrations tests."""
import os
import shutil
import time
from subprocess import Popen


class BlobStash(object):
    """BlobStash process manager. Expects `blobstash` to be available in $PATH."""

    def __init__(self, config=None, rebuild=True):
        self.process = None
        self.config = config or "blobstash.yaml"

    def run(self, reindex=False, log_level="error"):
        """Execute `blobsfs-mount {fs_name} {fs_name}` and return the running process."""
        cmd = ["blobstash", "--loglevel", log_level]
        if reindex:
            cmd.append("-scan")
        cmd.append(self.config)
        self.process = Popen(cmd, env=os.environ)
        time.sleep(1)
        if self.process.poll():
            raise Exception("failed to mount")

    def cleanup(self):
        """Cleanup func."""
        try:
            shutil.rmtree("blobstash_data")
        except Exception:
            pass

    def shutdown(self):
        """Perform a clean shutdown."""
        if self.process:
            self.process.terminate()
            self.process.wait()
