# gcp-oidc-proxy

Google Cloud Function for proxying requests to OIDC-authenticated endpoints.

## Deployment

```sh
$ gcloud functions deploy gcp-oidc-proxy \
    --runtime python37 \
    --entry-point handle_request \
    --trigger-http
```
