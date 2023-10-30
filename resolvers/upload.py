import os
import shutil
import tempfile
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from starlette.responses import JSONResponse

STORJ_ACCESS_KEY = os.environ.get("STORJ_ACCESS_KEY")
STORJ_SECRET_KEY = os.environ.get("STORJ_SECRET_KEY")
STORJ_END_POINT = os.environ.get("STORJ_END_POINT")
STORJ_BUCKET_NAME = os.environ.get("STORJ_BUCKET_NAME")
CDN_DOMAIN = os.environ.get("CDN_DOMAIN")


async def upload_handler(request):
    form = await request.form()
    file = form.get("file")

    if file is None:
        return JSONResponse({"error": "No file uploaded"}, status_code=400)

    file_name, file_extension = os.path.splitext(file.filename)

    key = "files/" + str(uuid.uuid4()) + file_extension

    # Create an S3 client with Storj configuration
    s3 = boto3.client(
        "s3",
        aws_access_key_id=STORJ_ACCESS_KEY,
        aws_secret_access_key=STORJ_SECRET_KEY,
        endpoint_url=STORJ_END_POINT,
    )

    try:
        # Save the uploaded file to a temporary file
        with tempfile.NamedTemporaryFile() as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)

            s3.upload_file(
                Filename=tmp_file.name,
                Bucket=STORJ_BUCKET_NAME,
                Key=key,
                ExtraArgs={"ContentType": file.content_type},
            )

        url = "https://" + CDN_DOMAIN + "/" + key

        return JSONResponse({"url": url, "originalFilename": file.filename})

    except (BotoCoreError, ClientError) as e:
        print(e)
        return JSONResponse({"error": "Failed to upload file"}, status_code=500)
