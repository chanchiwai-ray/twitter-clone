# Minimalist Twitter Clone

A minialist clone of Twitter.

## Required Environment Variables

- APP_SECRET_KEY
- GOOGLE_CLIENT_ID
- OAUTH_REDIRECT_URL (make sure to match the one in your gcp)
- OAUTH_CLIENT_SECRET_PATH
- OAUTHLIB_INSECURE_TRANSPORT (make sure to set it to 0 for production else 1)
- REDIS_PROD_HOST
- REDIS_PROD_PORT
- S3_BUCKET_NAME

## Optional Environment Variables (You may need them for local development)

- AWS_ACCESS_KEY
- AWS_SECRET_KEY
- S3_PROD_ENDPOINT_URL

## Docker Compose

You need to put the above environment variable into a hidden file called .env which will be used to build the app.

