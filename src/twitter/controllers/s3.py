import os
import boto3
from botocore.exceptions import ClientError


class EnvironmentNotSet(Exception):
    pass


class AccessDenied(Exception):
    pass


# not required, but you can customize the if you want (or when doing local development, they might be required)
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
S3_PROD_ENDPOINT_URL = os.environ.get("S3_PROD_ENDPOINT_URL")
S3_KWARGS = {}
if AWS_SECRET_KEY and AWS_ACCESS_KEY:
    S3_KWARGS.update(
        {
            "aws_access_key_id": AWS_ACCESS_KEY,
            "aws_secret_access_key": AWS_SECRET_KEY,
        }
    )
if S3_PROD_ENDPOINT_URL:
    S3_KWARGS.update({"endpoint_url": S3_PROD_ENDPOINT_URL})
# required
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
if not BUCKET_NAME:
    raise EnvironmentNotSet("BUCKET_NAME must be set to access aws s3 bucket!")


class S3Client(object):
    def __init__(self, bucket_name=BUCKET_NAME):
        self._bucket = bucket_name
        self._client = boto3.client(
            "s3",
            **S3_KWARGS,
        )
        # check if the bucket exist or not
        try:
            self._client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response["Error"]["Code"])
            if error_code == 403:
                raise AccessDenied("Private Bucket. Forbidden Access!")
            elif error_code == 404:
                self._client.create_bucket(Bucket=bucket_name, ACL="private")
            else:
                raise e

    def create_presigned_url(self, key, expires_in=3600):
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def upload_fileobj(self, file, key):
        return self._client.upload_fileobj(file.stream, self._bucket, str(key))

    def delete_file(self, key):
        return self._client.delete_object(Bucket=self._bucket, Key=key)

    def reset_s3(self):
        boto3.resource("s3", **S3_KWARGS).Bucket(self._bucket).objects.all().delete()
