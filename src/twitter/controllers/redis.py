import os
import redis


# basically only use for handling log in and other generic operartions
class RedisClient(object):
    def __init__(self):
        self._conn = redis.Redis(
            host=os.environ.get("REDIS_PROD_HOST", "localhost"),
            port=os.environ.get("REDIS_PROD_PORT", 6379),
            decode_responses=True,
        )
        self._check_alive()

    @property
    def conn(self):
        return self._conn

    def validate_session_id(self, sid):
        if not self.conn.hmget(sid, "email")[0]:
            return False
        return True

    def validate_user_id(self, uid):
        return self.conn.sismember("uids", uid)

    def get_user_id(self, sid):
        uid = self.conn.hget("users", self.conn.hmget(sid, "email")[0])
        if not self.validate_user_id(uid):
            return {"success": False, "payload": None}
        return {"success": True, "payload": uid}

    def reset_db(self):
        self.conn.flushall()

    def _check_alive(self):
        return self._conn.ping()
