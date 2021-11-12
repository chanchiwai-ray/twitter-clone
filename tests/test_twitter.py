import pytest
import uuid
from werkzeug.datastructures import FileStorage

from twitter.controllers.tweets import Tweet
from twitter.controllers.s3 import S3Client
from twitter.controllers.redis import RedisClient
from twitter.controllers.users import LoggedInUser


class ConnectionError(Exception):
    pass


@pytest.fixture(scope="module")
def sid_1():
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
def sid_2():
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
def fake_user_1():
    return {
        "uid": "1",
        "email": "fakeuser1@fakeemail.com",
        "family_name": "fake",
        "given_name": "user 1",
        "name": "user 1 fake",
        "locale": "en",
        "picture": "fake_image.png",
    }


@pytest.fixture(scope="module")
def fake_user_2():
    return {
        "uid": "2",
        "email": "fakeuser2@fakeemail.com",
        "family_name": "fake",
        "given_name": "user 2",
        "name": "user 2 fake",
        "locale": "en",
        "picture": "fake_image.png",
    }


@pytest.fixture(scope="module")
def redis_client():
    try:
        # setup
        client = RedisClient()
        # yield
        yield client
        # tear down
        client.reset_db()
    except:
        raise ConnectionError("Cannot connect to redis server...")


@pytest.fixture(scope="module")
def s3_client(redis_client):
    try:
        # setup
        client = S3Client()
        # yield
        yield client
        # tear down
        client.reset_s3()
    except:
        raise ConnectionError("Cannot connect to minio server...")


@pytest.fixture(scope="module")
def signup(redis_client, sid_1, sid_2, fake_user_1, fake_user_2):
    for sid, fake_user in zip([sid_1, sid_2], [fake_user_1, fake_user_2]):
        redis_client.conn.sadd("emails", fake_user["email"])
        redis_client.conn.sadd("uids", fake_user["uid"])
        # users:<uid> --> user info
        redis_client.conn.hset(
            f"users:{fake_user['uid']}",
            mapping={
                "uid": fake_user["uid"],
                "email": fake_user["email"],  # email should always exists
                "family_name": fake_user["family_name"],
                "given_name": fake_user["given_name"],
                "name": fake_user["name"],
                "locale": fake_user["locale"],
                "picture": fake_user["picture"],
            },
        )
        # [users] email--> uid
        redis_client.conn.hset("users", fake_user["email"], fake_user["uid"])

        # save the email and access token to the database: sid --> {email, access token}
        # use sid as access token
        redis_client.conn.hset(
            sid,
            mapping={"email": fake_user["email"], "token": sid},
        )


@pytest.fixture(scope="module")
def logged_in_user_1(redis_client, s3_client, signup, sid_1):
    user = LoggedInUser(sid_1, redis_client=redis_client, s3_client=s3_client)
    return user


@pytest.fixture(scope="module")
def logged_in_user_2(redis_client, s3_client, signup, sid_2):
    user = LoggedInUser(sid_2, redis_client=redis_client, s3_client=s3_client)
    return user


def test_post_and_get_tweet_without_image(logged_in_user_1, redis_client, s3_client):
    # placeholder
    image = {"tweet_image": FileStorage(filename="")}
    kwargs = {"image": image, "tweet_text": "Hello World"}
    logged_in_user_1.post_tweet(**kwargs)
    # image key should be popped if there's no image
    kwargs.pop("image")

    # we just post one tweet
    assert len(logged_in_user_1.tweets) == 1
    augmented_tweet = Tweet(
        logged_in_user_1.tweets[0], redis_client=redis_client, s3_client=s3_client
    ).tweet
    # these are added when doing get / post tweet, so we don't need to check for it
    augmented_tweet.pop("timestamp")
    augmented_tweet.pop("tid")
    augmented_tweet.pop("uid")
    assert kwargs == augmented_tweet


def test_update_tweet_without_iamge(logged_in_user_1, redis_client, s3_client):
    # we only post one tweet
    tid = logged_in_user_1.tweets[0]
    # placeholder
    image = {"tweet_image": FileStorage(filename="")}
    kwargs = {"image": image, "tweet_text": "Hello Earth"}
    logged_in_user_1.update_tweet(tid, **kwargs)
    # image key should be popped if there's no image
    kwargs.pop("image")

    # we just post one tweet
    assert len(logged_in_user_1.tweets) == 1
    augmented_tweet = Tweet(
        logged_in_user_1.tweets[0], redis_client=redis_client, s3_client=s3_client
    ).tweet
    # these are added when doing get / post tweet, so we don't need to check for it
    augmented_tweet.pop("timestamp")
    augmented_tweet.pop("tid")
    augmented_tweet.pop("uid")
    assert kwargs == augmented_tweet


def test_delete_tweet(logged_in_user_1):
    # we only post one tweet
    tid = logged_in_user_1.tweets[0]
    logged_in_user_1.del_tweet(tid)
    assert len(logged_in_user_1.tweets) == 0


def test_tweet_with_unsupported_image(logged_in_user_1):
    from pathlib import Path

    filename = str(Path(__file__).parent / "test_image_unsupported.svg")
    f = open(filename, "rb")
    image = {"tweet_image": FileStorage(f)}
    kwargs = {"image": image, "tweet_text": "Hello World"}
    # (post)
    assert not logged_in_user_1.post_tweet(**kwargs)
    assert len(logged_in_user_1.tweets) == 0
    f.close()


def test_tweet_with_fake_image(logged_in_user_1):
    from pathlib import Path

    filename = str(Path(__file__).parent / "test_fake_image.jpg")
    f = open(filename, "rb")
    image = {"tweet_image": FileStorage(f)}
    kwargs = {"image": image, "tweet_text": "Hello World"}
    # (post)
    assert not logged_in_user_1.post_tweet(**kwargs)
    assert len(logged_in_user_1.tweets) == 0
    f.close()


def test_tweet_with_supported_image(logged_in_user_1, redis_client, s3_client):
    from pathlib import Path

    filename = str(Path(__file__).parent / "test_image_supported.jpg")
    f = open(filename, "rb")
    image = {"tweet_image": FileStorage(f)}
    kwargs = {"image": image, "tweet_text": "Hello World"}
    # (post)
    assert logged_in_user_1.post_tweet(**kwargs)

    # (get)
    assert len(logged_in_user_1.tweets) == 1
    augmented_tweet = Tweet(
        logged_in_user_1.tweets[0], redis_client=redis_client, s3_client=s3_client
    ).tweet
    # these are added when doing get / post tweet, so we don't need to check for it
    augmented_tweet.pop("timestamp")
    augmented_tweet.pop("tid")
    augmented_tweet.pop("uid")
    # we can't test the image value as they are being replaced by presigned url
    assert (
        kwargs["tweet_text"] == augmented_tweet["tweet_text"]
        and kwargs.keys() == augmented_tweet.keys()
    )
    # (delete)
    tid = logged_in_user_1.tweets[0]
    logged_in_user_1.del_tweet(tid)
    assert len(logged_in_user_1.tweets) == 0
    f.close()


def test_follow(logged_in_user_1, logged_in_user_2):
    assert logged_in_user_1.follow(logged_in_user_2.uid)
    assert len(logged_in_user_2.followers) == 1


def test_unfollow(logged_in_user_1, logged_in_user_2):
    assert logged_in_user_1.unfollow(logged_in_user_2.uid)
    assert len(logged_in_user_2.following) == 0


def test_follow_or_unfollow_self(logged_in_user_1):
    assert not logged_in_user_1.follow(logged_in_user_1.uid)
    assert not logged_in_user_1.unfollow(logged_in_user_1.uid)
