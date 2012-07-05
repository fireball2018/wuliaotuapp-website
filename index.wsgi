#!/usr/bin/env python
# encoding: utf-8

import tornado.wsgi
import tornado.database

import sae
import os
import sys

import handlers

# 设置系统编码为utf8
code = sys.getdefaultencoding()
if code != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')

class Application(tornado.wsgi.WSGIApplication):
    def __init__(self):
        urls = [
            (r"/", handlers.index),
            (r"/index\.(json|html|xml)", handlers.index),
            (r'/fetch_jandan/?([0-9]+)?$', handlers.fetch_jandan),
            (r'/download_image', handlers.download_image),
            (r"/install", handlers.install),
            (r"/(.+)$", handlers._404),
        ]
        settings = dict(
            template_path = os.path.join(os.path.dirname(__file__), "view"),
            static_path = os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies = False,
            cookie_secret = "11oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url = "/auth/login",
            autoescape = None,
            debug = True,
            gzip = True,
        )
        tornado.wsgi.WSGIApplication.__init__(self, urls, **settings)

        # Have one global connection to the DB across all handlers
        self.db = tornado.database.Connection(
                host = sae.const.MYSQL_HOST + ':' + sae.const.MYSQL_PORT, 
                database = sae.const.MYSQL_DB,
                user = sae.const.MYSQL_USER, 
                password = sae.const.MYSQL_PASS, 
                max_idle_time = 5 )

application = sae.create_wsgi_app(Application())