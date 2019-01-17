from flask import Flask, request

from main import handle_request


app = Flask(__name__)


def wrapper():
    return handle_request(request)


wrapper.provide_automatic_options = False
wrapper.methods = ['GET', 'POST', 'PUT', 'DELETE']
app.add_url_rule('/', 'index', wrapper)

if __name__ == '__main__':
    app.run()
