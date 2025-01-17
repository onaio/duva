import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class S3Client:
    """
    This class encapsulates s3 client provided by boto3

    """

    s3 = boto3.resource("s3", region_name=settings.S3_REGION)

    def upload(self, path, file_name):
        """
        uploads file in the given path to s3 with the given filename
        """
        try:
            self.s3.meta.client.upload_file(path, settings.S3_BUCKET, file_name)
        except ClientError:
            return False
        return True

    def download(self, path, file_name):
        """
        Downloads file_name in s3 to path
        """
        try:
            self.s3.meta.client.download_file(settings.S3_BUCKET, file_name, path)
        except ClientError:
            return False
        return True

    def delete(self, file_path):
        """
        Deletes file_path in S3
        """
        try:
            resp = self.s3.meta.client.delete_object(
                Bucket=settings.S3_BUCKET, Key=file_path
            )
        except ClientError:
            return False
        else:
            status = resp.get("ResponseMetadata").get("HTTPStatusCode")
            return status == 204 or "DeleteMarker" in resp.keys()

    def generate_presigned_download_url(self, file_path: str, expiration: int = 3600):
        """
        Generates a presigned Download URL

        file_path :string: Path to the file in the S3 Bucket
        expirationg :integer: The duration in seconds that the URL should be valid for
        """
        try:
            response = self.s3.meta.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET, "Key": file_path},
                ExpiresIn=expiration,
            )
        except ClientError:
            return None
        return response
