import ipaddress
from urllib.parse import unquote, urlsplit, urlunsplit


def validate_https_repository_url(repository_url):
    if not isinstance(repository_url, str) or not repository_url.strip():
        raise ValueError('A repository URL is required.')

    value = repository_url.strip()
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise ValueError('Enter a valid HTTPS repository URL.') from exc

    if (
        parsed.scheme.lower() != 'https'
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError('Enter a public HTTPS repository URL without credentials or query parameters.')

    host = hostname.lower().rstrip('.')
    if host in {'localhost', 'localhost.localdomain'} or host.endswith(
        ('.localhost', '.local', '.internal', '.test', '.invalid')
    ):
        raise ValueError('Repository URLs must use a public host.')

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or '..' in host:
            raise ValueError('Enter a valid public repository host.')
    else:
        if not address.is_global:
            raise ValueError('Repository URLs must use a public host.')

    segments = [unquote(part) for part in parsed.path.split('/') if part]
    if len(segments) < 2 or any(part in {'.', '..'} or '/' in part or '\\' in part for part in segments):
        raise ValueError('Repository URL must identify a repository path.')

    return urlunsplit(('https', parsed.netloc, '/' + '/'.join(segments), '', ''))
