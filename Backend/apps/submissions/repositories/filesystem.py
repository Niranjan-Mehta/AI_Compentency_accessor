"""Filesystem cleanup for temporary repository checkouts."""

import os
import shutil
import stat
from pathlib import Path


def remove_repository_directory(path):
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        path.unlink()
        return

    def retry_after_clearing_readonly(function, filename, _error):
        os.chmod(filename, stat.S_IREAD | stat.S_IWRITE)
        function(filename)

    shutil.rmtree(path, onerror=retry_after_clearing_readonly)
