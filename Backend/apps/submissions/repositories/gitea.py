from .public_git import PublicGitProvider
from .url_validation import validate_https_repository_url


class GiteaProvider(PublicGitProvider):
    """Gitea URL provider; API credentials and remote operations are deferred."""

    def validate_repository_url(self, repository_url):
        return validate_https_repository_url(repository_url)
