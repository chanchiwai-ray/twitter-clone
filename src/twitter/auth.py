import os
import flask
import functools
from requests import post
from pathlib import Path

from twitter.controllers.redis import RedisClient

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow


#
# Constants
#

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET_PATH = Path(os.environ["OAUTH_CLIENT_SECRET_PATH"])
OAUTH_REDIRECT_URL = os.environ["OAUTH_REDIRECT_URL"]
if not CLIENT_SECRET_PATH.exists():
    raise ValueError(
        "OAUTH_CLIENT_SECRET_PATH is either not set or the file does not exist in the application root directory."
    )

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

redis_client = RedisClient()

#
# auth.py: module's entry point
#

blueprint = flask.Blueprint("auth", __name__, url_prefix="/auth")


@blueprint.before_app_request
def get_session_id():
    # store the session id in flask if it exists in the session cookies,
    # and use it to retrive the credentials from the database
    flask.g.sid = flask.session.get("sid")


@blueprint.route("/login")
def login():
    if not flask.g.sid:
        return flask.render_template("auth/login.html")
    return flask.redirect(flask.url_for("home"))


@blueprint.route("/logout")
def logout():
    # Clear the credential in the database and revoke the access token
    sid = flask.g.sid
    if not sid:
        return flask.redirect(flask.url_for("home"))
    (token,) = redis_client.conn.hmget(sid, "token")
    if not token:
        return flask.redirect(flask.url_for("home"))
    post(
        "https://oauth2.googleapis.com/revoke",
        params={"token": token},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    redis_client.conn.hdel(sid, "token", "email")
    # Clear the session
    flask.session.clear()
    # Redirect back to index page
    return flask.redirect(flask.url_for("home"))


@blueprint.route("/oauth2/login")
def google_login():
    if not flask.g.sid:
        return _flow_redirect(OAUTH_REDIRECT_URL)
    return flask.redirect(flask.url_for("home"))


@blueprint.route("/oauth2/login/callback")
def google_login_callback():
    # install the credentials to session
    credentials = _flow_install(OAUTH_REDIRECT_URL)

    req = google_requests.Request()
    id_info = id_token.verify_oauth2_token(
        credentials._id_token, req, audience=GOOGLE_CLIENT_ID
    )

    # (sign up)
    # email should be enough to uniquely identified a user x
    if not redis_client.conn.sismember("emails", id_info["email"]):
        # keep a set of emails which is used to identify the user
        redis_client.conn.sadd("emails", id_info["email"])
        uid = redis_client.conn.incr("uid")
        redis_client.conn.sadd("uids", uid)

        # users:<uid> --> user info
        redis_client.conn.hmset(
            f"users:{uid}",
            {
                "uid": uid,
                "email": id_info["email"],  # email should always exists
                "family_name": id_info.get("family_name"),
                "given_name": id_info.get("given_name"),
                "name": id_info.get("name"),
                "locale": id_info.get("locale"),
                "picture": id_info.get("picture"),
            },
        )
        # [users] email--> uid
        redis_client.conn.hset("users", id_info["email"], uid)

        # save the session id in the session cookies
        flask.session["sid"] = os.urandom(64)
        # save the email and access token to the database: sid --> {email, access token}
        redis_client.conn.hmset(
            flask.session["sid"],
            {"email": id_info["email"], "token": credentials.token},
        )

        # delegate to index page to handle other redirection
        return flask.redirect(flask.url_for("home"))

    # (log in)
    # save the session id in the session cookies
    flask.session["sid"] = os.urandom(64)
    # save the email and access token to the database: sid --> {email, access token}
    redis_client.conn.hmset(
        flask.session["sid"], {"email": id_info["email"], "token": credentials.token}
    )

    # delegate to home page to handle other redirection
    return flask.redirect(flask.url_for("home"))


#
# Utilities
#


# check to see if the user is a logged in users only
def protect(view):
    @functools.wraps(view)
    def protected_view(**kwargs):
        # check session id exists or not
        if flask.g.sid is None and view.__name__ == "home":
            return flask.render_template("index.html")
        elif flask.g.sid is None:
            return flask.render_template("error/403.html")
        # if exists, validate session id
        elif not redis_client.validate_session_id(flask.g.sid):
            flask.session.clear()
            flask.abort(400, "Unexpected Client Side Error.")
        return view(**kwargs)

    return protected_view


#
# Internal helper function
#


def _flow_redirect(url):
    flow = Flow.from_client_secrets_file(CLIENT_SECRET_PATH, scopes=SCOPES)
    flow.redirect_uri = url

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type="offline",
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes="true",
    )

    # Store the state so the callback can verify the auth server response.
    flask.session["state"] = state
    return flask.redirect(authorization_url)


def _flow_install(redirect_url):
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session["state"]

    if state != flask.request.args["state"]:
        flask.abort(400)

    flow = Flow.from_client_secrets_file(CLIENT_SECRET_PATH, scopes=SCOPES, state=state)
    flow.redirect_uri = redirect_url

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    credentials = flow.credentials

    return credentials
