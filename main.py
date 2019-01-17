import os
import time

import google.auth
from google.auth.transport.requests import Request as GRequest
from google.oauth2.service_account import Credentials
import jwt
from requests import Request
from requests import Session


IAM_SCOPE = 'https://www.googleapis.com/auth/iam'
OAUTH_TOKEN_URI = 'https://www.googleapis.com/oauth2/v4/token'
HOST_HEADER = 'Forward-Host'

_oidc_token = None
_session = Session()
_adc_credentials, _ = google.auth.default(scopes=[IAM_SCOPE])

_whitelist = os.getenv('WHITELIST', [])
if _whitelist:
    _whitelist = [p.strip() for p in _whitelist.split(',')]

# For service accounts using the Compute Engine metadata service, which is the
# case for Cloud Function service accounts, service_account_email isn't
# available until refresh is called.
_adc_credentials.refresh(GRequest())

# Since the Compute Engine metadata service doesn't expose the service
# account key, we use the IAM signBlob API to sign instead. In order for this
# to work, the Cloud Function's service account needs the "Service Account
# Actor" role.
_signer = google.auth.iam.Signer(
    GRequest(), _adc_credentials, _adc_credentials.service_account_email)


class OIDCToken(object):

    def __init__(self, token_str):
        self._token_str = token_str
        self._claims = jwt.decode(token_str, verify=False)

    def __str__(self):
        return self._token_str

    def is_expired(self):
        return int(time.time()) >= self._claims['exp']


def handle_request(proxied_request):
    """Proxy the given request to the URL in the Forward-Host header with an
    Authorization header set using an OIDC bearer token for the Cloud
    Function's service account. If the header is not present, return a 400
    error.
    """

    host = proxied_request.headers.get(HOST_HEADER)
    if not host:
        return 'Required header {} not present'.format(HOST_HEADER), 400

    scheme = proxied_request.headers.get('X-Forwarded-Proto', 'https')
    url = '{}://{}{}'.format(scheme, host, proxied_request.path)
    headers = dict(proxied_request.headers)

    # Check path against whitelist.
    path = proxied_request.path
    if not path:
        path = '/'
    # TODO: Implement proper wildcarding for paths.
    if '*' not in _whitelist and path not in _whitelist:
        print('Rejected {} {}, not in whitelist'.format(
            proxied_request.method, url))
        return 'Requested path {} not in whitelist'.format(path), 403

    global _oidc_token
    if not _oidc_token or _oidc_token.is_expired():
        _oidc_token = _get_google_oidc_token()
        print('Renewed OIDC bearer token for {}'.format(
            _adc_credentials.service_account_email))

    # Add the Authorization header with the OIDC token.
    headers['Authorization'] = 'Bearer {}'.format(_oidc_token)

    # We don't want to forward the Host header.
    headers.pop('Host', None)
    request = Request(proxied_request.method, url,
                      headers=headers,
                      data=proxied_request.data)

    # Send the proxied request.
    prepped = request.prepare()
    print('{} {}'.format(prepped.method, prepped.url))
    resp = _session.send(prepped)

    # Strip hop-by-hop headers and Content-Encoding.
    headers = _strip_hop_by_hop_headers(resp.headers)
    headers.pop('Content-Encoding', None)

    return resp.content, resp.status_code, headers.items()


def _get_google_oidc_token():
    """Get an OpenID Connect token issued by Google for the environment's
    service account.

    This function:
      1. Generates a JWT signed with the service account's private key
         containing a special "target_audience" claim.

      2. Sends it to the OAUTH_TOKEN_URI endpoint. Because the JWT in #1
         has a target_audience claim, that endpoint will respond with
         an OpenID Connect token for the service account -- in other words,
         a JWT signed by *Google*. The aud claim in this JWT will be
         set to the value from the target_audience claim in #1.

    For more information, see
    https://developers.google.com/identity/protocols/OAuth2ServiceAccount .
    The HTTP/REST example on that page describes the JWT structure and
    demonstrates how to call the token endpoint. (The example on that page
    shows how to get an OAuth2 access token; this code is using a
    modified version of it to get an OpenID Connect token.)
    """

    credentials = Credentials(
        _signer, _adc_credentials.service_account_email,
        token_uri=OAUTH_TOKEN_URI,
        additional_claims={'target_audience': os.getenv('CLIENT_ID')}
    )
    service_account_jwt = credentials._make_authorization_grant_assertion()
    request = GRequest()
    body = {
        'assertion': service_account_jwt,
        'grant_type': google.oauth2._client._JWT_GRANT_TYPE,
    }
    token_response = google.oauth2._client._token_endpoint_request(
        request, OAUTH_TOKEN_URI, body)
    return OIDCToken(token_response['id_token'])


_hoppish = {
    'connection': 1,
    'keep-alive': 1,
    'proxy-authenticate': 1,
    'proxy-authorization': 1,
    'te': 1,
    'trailers': 1,
    'transfer-encoding': 1,
    'upgrade': 1,
}.__contains__


def _is_hop_by_hop(header_name):
    """Return True if 'header_name' is an HTTP/1.1 "Hop-by-Hop" header."""
    return _hoppish(header_name.lower())


def _strip_hop_by_hop_headers(headers):
    """Return a dict with HTTP/1.1 "Hop-by-Hop" headers removed."""
    return {k: v for (k, v) in headers.items() if not _is_hop_by_hop(k)}

