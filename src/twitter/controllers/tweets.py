import os
import imghdr
from werkzeug.utils import secure_filename

from twitter.controllers import s3
from twitter.controllers import redis

# allow file extension
ALLOWED_UPLOAD_EXTENSIONS = (".jpg", ".png", ".gif", ".jpeg")


class Tweet(object):
    def __init__(self, tid, s3_client=None, redis_client=None):
        self._tid = tid
        self._s3_client = s3_client or s3.S3Client()
        self._redis_client = redis_client or redis.RedisClient()

    # uid of the user that post the tweet
    @property
    def uid(self):
        return self.tweet["uid"]

    # the tweet id
    @property
    def tid(self):
        return self._tid

    # the content of the tweet
    @property
    def tweet(self):
        tweet = self._redis_client.conn.hgetall(f"tweets:{self.tid}")
        tweet.update(
            {
                "timestamp": float(tweet["timestamp"]),
                "tid": self.tid,
            }
        )
        # if the tweet contains image, then also grab that as presigned_url
        if "image" in tweet:
            tweet.update(
                {"image": self._s3_client.create_presigned_url(tweet["image"])}
            )
        return tweet

    def is_exist(self):
        return self._redis_client.conn.sismember("tids", self.tid)


#
# Utilities
#


def get_all_tweets_ids():
    client = redis.RedisClient()
    return list(client.conn.smembers("tids"))


def is_valid_file(file):
    filename = secure_filename(file.filename)
    omote_extension = os.path.splitext(filename)[1]
    ura_extension = imghdr.what(
        file.stream
    )  # this will only check limited kinds of image types
    if (
        omote_extension not in ALLOWED_UPLOAD_EXTENSIONS
        or ura_extension is None
        or f".{ura_extension}" not in ALLOWED_UPLOAD_EXTENSIONS
    ):
        return False
    return True
