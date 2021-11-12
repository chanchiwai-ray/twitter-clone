from twitter.app import app


def main(*args):
    app.run(
        host="localhost",
        port=5000,
    )


if __name__ == "__main__":
    app.run()
