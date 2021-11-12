import os
import flask

from twitter import auth
from twitter.controllers import s3 as controllers_s3
from twitter.controllers import redis as controllers_redis
from twitter.controllers import users as controllers_users
from twitter.controllers import tweets as controllers_tweets


#
# app entry point
#

app = flask.Flask(__name__)
app.secret_key = os.environ["APP_SECRET_KEY"]
app.config["MAX_CONTENT_LENGTH"] = os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)
app.register_blueprint(auth.blueprint)

s3_client = controllers_s3.S3Client()
redis_client = controllers_redis.RedisClient()

# personal home page
@app.route("/")
@auth.protect
def home():
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )

    uid = current_user.uid
    tids = controllers_tweets.get_all_tweets_ids()
    # user info
    logged_in_user = current_user.profile
    # just grab the info we need
    logged_in_user.update({"following_uids": current_user.following})
    logged_in_user.update({"num_of_following": len(current_user.following)})
    logged_in_user.update({"num_of_followers": len(current_user.followers)})
    # tweets
    tweets = []
    for tid in tids:
        tweet = controllers_tweets.Tweet(tid)
        # extract the content
        content = tweet.tweet
        content.update({"user": controllers_users.User(tweet.uid).profile})
        tweets.append(content)
    tweets.sort(key=lambda x: x["timestamp"], reverse=True)
    # all unfollowed users
    uids = controllers_users.get_all_users_ids()
    users = []
    for uid in set(uids) - set(current_user.following) - set(current_user.uid):
        user = controllers_users.User(uid).profile
        users.append(user)
    return flask.render_template(
        "home.html",
        logged_in_user=logged_in_user,
        user=logged_in_user,
        users=users,
        tweets=tweets,
    )


# personal profile page
@app.route("/profile")
@auth.protect
def profile():
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )
    logged_in_user = current_user.profile
    # get current user's followers and following
    logged_in_user.update({"following_uids": current_user.following})
    logged_in_user.update({"num_of_following": len(current_user.following)})
    logged_in_user.update({"num_of_followers": len(current_user.followers)})
    following_users = []
    for uid in current_user.following:
        user = controllers_users.User(uid).profile
        following_users.append(user)
    followers = []
    for uid in current_user.followers:
        user = controllers_users.User(uid).profile
        user.update({"is_following": uid in current_user.following})
        followers.append(user)
    # personal tweets (yourself and following uids)
    uids = current_user.following
    uids.append(current_user.uid)
    tweets = []
    for user_id in uids:
        tids = controllers_users.User(user_id).tweets
        for tid in tids:
            tweet = controllers_tweets.Tweet(tid)
            # extract the content
            content = tweet.tweet
            content.update({"user": controllers_users.User(tweet.uid).profile})
            tweets.append(content)
    tweets.sort(key=lambda x: x["timestamp"], reverse=True)
    return flask.render_template(
        "profile.html",
        logged_in_user=logged_in_user,
        user=logged_in_user,
        following_users=following_users,
        followers=followers,
        tweets=tweets,
    )


# get users' profile page
@app.route("/users/<int:uid>/profile")
@auth.protect
def guest_profile(uid):
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )
    logged_in_user = current_user.profile
    logged_in_user.update({"following": str(uid) in current_user.following})
    logged_in_user.update({"following_uids": current_user.following})
    # get visiting user's info, followers, and following
    visiting_user = controllers_users.User(uid)
    if not visiting_user.is_exist():
        return flask.render_template("error/404.html"), 404
    user = visiting_user.profile
    user.update({"num_of_following": len(visiting_user.following)})
    user.update({"num_of_followers": len(visiting_user.followers)})
    # get visting user's tweets
    tids = visiting_user.tweets
    tweets = []
    for tid in tids:
        tweet = controllers_tweets.Tweet(tid)
        # extract the content
        content = tweet.tweet
        content.update({"user": controllers_users.User(tweet.uid).profile})
        tweets.append(content)
    tweets.sort(key=lambda x: x["timestamp"], reverse=True)
    return flask.render_template(
        "profile.html",
        logged_in_user=logged_in_user,
        user=user,
        tweets=tweets,
    )


# get all tweet images
@app.route("/gallery")
@auth.protect
def gallery():
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )

    uid = current_user.uid
    tids = controllers_tweets.get_all_tweets_ids()
    # user info
    logged_in_user = current_user.profile
    # tweets
    tweets = []
    for tid in tids:
        tweet = controllers_tweets.Tweet(tid)
        # extract the content
        content = tweet.tweet
        content.update({"user": controllers_users.User(tweet.uid).profile})
        tweets.append(content)
    # all unfollowed users
    uids = controllers_users.get_all_users_ids()
    users = []
    for uid in set(uids) - set(current_user.following) - set(current_user.uid):
        user = controllers_users.User(uid).profile
        users.append(user)
    return flask.render_template(
        "gallery.html",
        logged_in_user=logged_in_user,
        user=logged_in_user,
        tweets=tweets,
    )


# get other Users
@app.route("/people")
@auth.protect
def people():
    uids = controllers_users.get_all_users_ids()
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )
    uids.remove(current_user.uid)
    logged_in_user = current_user.profile

    users = []
    for user_id in uids:
        user = controllers_users.User(user_id).profile
        user.update(
            {
                "following": redis_client.conn.sismember(
                    f"following:{current_user.uid}", user_id
                ),
            }
        )
        users.append(user)
    return flask.render_template(
        "people.html", logged_in_user=logged_in_user, users=users
    )


# follow / unfollow
@app.route("/users/<int:uid>/following", methods=["POST"])
@auth.protect
def following(uid):
    # check if the logged in user is doing something unexpected, e.g. follow / unfollow non-existing user
    if not redis_client.validate_user_id(uid):
        flask.abort(400, "Unexpected Client Side Error.")
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )
    method = flask.request.form.get("_method")
    if method == "follow":
        if not current_user.follow(uid):
            flask.abort(500, "Unexpected Server Side Error.")
    elif method == "unfollow":
        if not current_user.unfollow(uid):
            flask.abort(500, "Unexpected Server Side Error.")
    else:
        flask.abort(500, "Unexpected Server Side Error.")
    return flask.redirect(flask.request.form.get("_redirect"))


# new tweet page
@app.route("/tweet/new", methods=["GET"])
@auth.protect
def new_tweet_form():
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )
    return flask.render_template("add_tweet.html", user=current_user.profile)


# post tweet
@app.route("/tweets", methods=["POST"])
@auth.protect
def new_tweet():
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )
    if not current_user.post_tweet(**flask.request.form, image=flask.request.files):
        return f"<p>The uploaded image is not in an allowed format. Allowed Formats are {controllers_tweets.ALLOWED_UPLOAD_EXTENSIONS}"
    return flask.redirect(flask.url_for("home"))


# get tweet
@app.route("/tweets/<int:tid>", methods=["GET"])
@auth.protect
def get_tweet(tid):
    # get current user's info and followers
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )

    tweet = controllers_tweets.Tweet(tid)
    if not tweet.is_exist():
        return flask.abort(400, "Unexpected Client side error.")

    return flask.render_template(
        "tweet.html",
        logged_in_user=current_user.profile,
        user=controllers_users.User(tweet.uid).profile,
        old_form=tweet.tweet,
    )


# put and delete tweet
@app.route("/tweets/<int:tid>", methods=["POST"])
@auth.protect
def change_tweet(tid):
    current_user = controllers_users.LoggedInUser(
        flask.g.sid, redis_client=redis_client, s3_client=s3_client
    )

    tweet = controllers_tweets.Tweet(tid)
    if not tweet.is_exist():
        return flask.abort(400, "Unexpected Client side error.")

    method = flask.request.form.get("_method")
    if method == "PUT":
        if len(flask.request.form["tweet_text"]) > 500:
            flask.abort(400, "Exceeding maximum characters limit!")
        if not current_user.update_tweet(
            tid, **flask.request.form, image=flask.request.files
        ):
            flask.abort(500, "Server side error, update not suceess.")
    elif method == "DELETE":
        if not current_user.del_tweet(tid):
            flask.abort(500, "Server side error, delete not suceess.")
    else:
        flask.abort(500, "Server side error, update / delete not suceess.")
    return flask.redirect(flask.request.form.get("_redirect"))


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template("error/404.html"), 404
