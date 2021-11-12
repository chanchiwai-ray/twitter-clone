from datetime import datetime
from werkzeug.utils import secure_filename

from twitter.controllers import s3
from twitter.controllers import redis
from twitter.controllers.tweets import is_valid_file

#
# users.py: module's entry point
#


class InvalidSessionError(Exception):
    pass


class User(object):
    def __init__(self, uid, client=None):
        # create redis client
        self._redis_client = client or redis.RedisClient()
        # get user profile
        self._uid = uid
        self._profile = self._redis_client.conn.hgetall(f"users:{self._uid}")

    # user id
    @property
    def uid(self):
        return self._uid

    # in principle this should have 'set' method, but we don't change profile anyway
    @property
    def profile(self):
        return self._profile

    # followers uids
    @property
    def followers(self):
        return list(self._redis_client.conn.smembers(f"followers:{self.uid}"))

    # following users' uids
    @property
    def following(self):
        return list(self._redis_client.conn.smembers(f"following:{self.uid}"))

    # user's tweets' tids
    @property
    def tweets(self):
        return list(self._redis_client.conn.smembers(f"user:tweets:{self.uid}"))

    def is_exist(self):
        return self._redis_client.validate_user_id(self.uid)


class LoggedInUser(User):
    def __init__(self, sid, redis_client=None, s3_client=None):
        # get uid
        self._s3_client = s3_client or s3.S3Client()
        self._redis_client = redis_client or redis.RedisClient()
        self._uid = self._redis_client.get_user_id(sid)
        if not self._uid["success"]:
            raise InvalidSessionError("Your session is invalid!")
        self._uid = self._uid["payload"]
        super().__init__(self._uid, client=self._redis_client)
        # get user profile
        self._profile = self._redis_client.conn.hgetall(f"users:{self._uid}")

    # follow another user
    def follow(self, uid):
        if uid == self.uid:
            return False
        self._redis_client.conn.sadd(f"following:{self.uid}", uid)
        self._redis_client.conn.sadd(f"followers:{uid}", self.uid)
        return True

    # unfollow another user
    def unfollow(self, uid):
        if uid == self.uid:
            return False
        self._redis_client.conn.srem(f"following:{self.uid}", uid)
        self._redis_client.conn.srem(f"followers:{uid}", self.uid)
        return True

    # update the tweet content
    def update_tweet(self, tid, **kwargs):
        if not self._redis_client.conn.sismember(f"user:tweets:{self.uid}", tid):
            return False
        image = kwargs["image"].get("tweet_image")
        filename = secure_filename(image.filename)
        # have the image file but not valid
        if filename != "" and not is_valid_file(image):
            return False
        # have the image file and valid
        if filename != "":
            # get the image id if it exists, otherwise create one
            # get the iid if it exists (update image), otherwise create a new one (upload new image)
            iid = self._redis_client.conn.hget(f"tweets:{tid}", "image")
            if not iid:
                iid = f"{self._redis_client.conn.incr('iid')}_{filename}"
            # upload image with the key iid
            self._s3_client.upload_fileobj(image, iid)
            # store the image id in redis
            kwargs.update({"image": iid})
        # user did not upload an image
        else:
            # remove unwant kwarg
            kwargs.pop("image")
            # get the iid if it exists (update image), otherwise do nothing
            iid = self._redis_client.conn.hget(f"tweets:{tid}", "image")
            if iid:
                self._s3_client.delete_file(iid)
                self._redis_client.conn.hdel(f"tweets:{tid}", "image")
        # update timestamp
        kwargs.update({"timestamp": datetime.now().timestamp()})
        # update the tweet
        self._redis_client.conn.hset(f"tweets:{tid}", mapping=kwargs)
        return True

    def post_tweet(self, **kwargs):
        image = kwargs["image"].get("tweet_image")
        filename = secure_filename(image.filename)
        # have the image file but not valid
        if filename != "" and not is_valid_file(image):
            return False
        # update users's tweets
        tid = self._redis_client.conn.incr("tid")
        self._redis_client.conn.sadd("tids", tid)
        self._redis_client.conn.sadd(f"user:tweets:{self.uid}", tid)
        # create a id for image so that it can be refered by s3
        if filename != "":
            iid = f"{self._redis_client.conn.incr('iid')}_{filename}"
            # upload image with the key iid
            self._s3_client.upload_fileobj(image, iid)
            kwargs.update({"image": iid})
        else:
            # remove unwant kwarg
            kwargs.pop("image")
        # add auxiliary information
        kwargs.update({"timestamp": datetime.now().timestamp(), "uid": self.uid})
        # set tweet
        self._redis_client.conn.hset(f"tweets:{tid}", mapping=kwargs)
        return True

    def del_tweet(self, tid):
        if not self._redis_client.conn.sismember(f"user:tweets:{self.uid}", tid):
            return False
        # delete file if the tweets:{tid} has 'image'
        iid = self._redis_client.conn.hget(f"tweets:{tid}", "image")
        if iid:
            self._s3_client.delete_file(iid)
        # remove tid from all tids
        self._redis_client.conn.srem("tids", tid)
        # remove tid from the user's tids
        self._redis_client.conn.srem(f"user:tweets:{self.uid}", tid)
        # remove the tweet from the database
        for k in self._redis_client.conn.hgetall(f"tweets:{tid}").keys():
            self._redis_client.conn.hdel(f"tweets:{tid}", k)
        return True


#
# helper functions
#


def get_all_users_ids():
    client = redis.RedisClient()  # use default
    return [user_id for user_id in client.conn.hgetall("users").values()]
