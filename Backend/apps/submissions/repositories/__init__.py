from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .gitea import GiteaProvider
from .public_git import PublicGitProvider


PROVIDERS = {
    'public_git': PublicGitProvider,
    'gitea': GiteaProvider,
}


def get_repository_provider():
    provider_name = getattr(settings, 'REPOSITORY_PROVIDER', 'public_git').lower()
    provider_class = PROVIDERS.get(provider_name)
    if provider_class is None:
        raise ImproperlyConfigured(f'Unknown repository provider: {provider_name}')
    return provider_class()
