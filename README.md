# gcp-oidc-proxy

Google Cloud Function for proxying requests to
[OIDC-authenticated](https://openid.net/connect/) endpoints. For example, this
can be used to make authenticated requests to resources protected by a GCP
[Identity Aware Proxy (IAP)](https://cloud.google.com/iap/) using a service
account.

## Deployment

```sh
$ gcloud functions deploy gcp-oidc-proxy \
    --runtime python37 \
    --entry-point handle_request \
    --trigger-http
```

- The service account for the Cloud Function needs the "Service Account Actor
  IAM" role.
- A `CLIENT_ID` environment variable needs to be set containing the OAuth2
  client ID, e.g. the client ID used by IAP.
- A `WHITELIST` environment variable needs to be set containing a
  comma-separated list of paths to allow requests for. A value of `*` will
  whitelist all paths.
- The service account for the Cloud Function needs to be added as a member of
  the protected resource with appropriate roles configured.
- Optionally, Basic authentication can be enabled by setting `AUTH_USERNAME`
  and `AUTH_PASSWORD` environment variables. If either of these is not set,
  authentication is disabled.

## Local Development

You can run the function locally with:

```sh
$ python test.py
```

This will start an HTTP server which maps requests to the Cloud Function. This
requires setting the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to a
service account credentials file which has the IAM roles described above.
