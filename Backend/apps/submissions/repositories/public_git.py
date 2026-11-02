import ipaddress
import os
import socket
import subprocess
import time

from django.conf import settings

from .base import RepositoryProvider
from .filesystem import remove_repository_directory
from .url_validation import validate_https_repository_url


class PublicGitProvider(RepositoryProvider):
    """Provider for public repositories addressed by ordinary HTTPS URLs."""

    def validate_repository_url(self, repository_url):
        return validate_https_repository_url(repository_url)

    def clone_repository(self, repository_url, branch, destination):
        url = self.validate_repository_url(repository_url)
        self._assert_public_destination(url)
        if not branch or branch.startswith('-') or any(ord(char) < 32 for char in branch):
            raise ValueError('Invalid repository branch.')

        destination = os.fspath(destination)
        if os.path.exists(destination):
            raise ValueError('Repository destination must not already exist.')
        env = os.environ.copy()
        env.update({
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_TERMINAL_PROMPT': '0',
            'GIT_LFS_SKIP_SMUDGE': '1',
        })
        for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
            env.pop(key, None)

        command = [
            'git', '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
            '-c', 'http.followRedirects=false', '-c', 'http.sslVerify=true',
            'clone', '--depth', '1', '--single-branch', '--no-recurse-submodules',
            '--branch', branch, '--', url, destination,
        ]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        started = time.monotonic()
        while process.poll() is None:
            if time.monotonic() - started > settings.REPOSITORY_CLONE_TIMEOUT_SECONDS:
                process.kill()
                process.wait()
                remove_repository_directory(destination)
                raise ValueError('Repository clone timed out.')
            if os.path.exists(destination) and self._directory_size(destination) > settings.MAX_REPOSITORY_SIZE_BYTES:
                process.kill()
                process.wait()
                remove_repository_directory(destination)
                raise ValueError('Repository exceeds the configured size limit.')
            time.sleep(0.2)

        if process.returncode:
            remove_repository_directory(destination)
            raise ValueError('Repository could not be cloned. Check the URL and branch are publicly accessible.')
        if self._directory_size(destination) > settings.MAX_REPOSITORY_SIZE_BYTES:
            remove_repository_directory(destination)
            raise ValueError('Repository exceeds the configured size limit.')
        return subprocess.check_output(
            ['git', '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always', '-C', destination, 'rev-parse', 'HEAD'],
            env=env,
            text=True,
            timeout=10,
        ).strip()

    @staticmethod
    def _assert_public_destination(url):
        from urllib.parse import urlsplit

        parsed = urlsplit(url)
        if parsed.port not in (None, 443):
            raise ValueError('Repository URLs must use the standard HTTPS port.')
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise ValueError('Repository host could not be resolved.') from exc
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError('Repository host resolves to a private or internal network.')

    @staticmethod
    def _directory_size(path):
        total = 0
        for root, _, files in os.walk(path, followlinks=False):
            for filename in files:
                try:
                    total += os.path.getsize(os.path.join(root, filename))
                except OSError:
                    continue
        return total
