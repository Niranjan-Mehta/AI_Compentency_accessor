from abc import ABC, abstractmethod


class RepositoryProvider(ABC):
    """Provider-neutral URL validation and repository checkout contract."""

    @abstractmethod
    def validate_repository_url(self, repository_url):
        """Return a normalized URL or raise ValueError for an unsupported URL."""
        raise NotImplementedError

    @abstractmethod
    def clone_repository(self, repository_url, branch, destination):
        """Checkout a branch without executing repository content; return HEAD SHA."""
        raise NotImplementedError
