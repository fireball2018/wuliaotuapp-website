#!/usr/bin/env python
# encoding: utf-8

from __future__ import division

import os
import re
import urllib2
import hashlib
import time
import math

from PIL import Image
from StringIO import StringIO

import tornado.web

from sae.taskqueue import add_task
import pylibmc

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

from BeautifulSoup import BeautifulSoup

class BaseHandler(tornado.web.RequestHandler):
    """docstring for BaseHandler"""
    
    @property
    def db(self):
        return self.application.db

class _404(BaseHandler):
    """docstring for _404"""
    
    def get(self, url):
        
        self.write("404(/%s)" % url)
        
class index(BaseHandler):
    """docstring for index"""
    
    def get(self, format='html'):

        start = self.get_argument('start', 0)

        try:
            start = int(start)
        except Exception, e:
            start = 1

        limit = 20

        total = self.db.get("SELECT count(id) as total FROM pics WHERE width>0 and height>0")
        total = total['total']

        max_id = self.db.get("SELECT max(id) as max_id FROM pics WHERE width>0 and height>0")
        max_id = max_id['max_id']

        min_id = self.db.get("SELECT min(id) as min_id FROM pics WHERE width>0 and height>0")
        min_id = min_id['min_id']

        if start <= 1:
            start = max_id

        pics = self.db.query("SELECT * FROM pics WHERE id<%s and width>0 and height>0 ORDER BY id DESC LIMIT %s", start, limit)

        if format =='json':
            page_count = int(round(math.ceil(total/limit)))
            self.write({'pics':pics, 'total':total})
        else:
            self.render("index.html", pics=pics, max_id=max_id, min_id=min_id, limit=limit)

class update(BaseHandler):

    def get(self, format='json'):

        last_id = int(self.get_argument("id", 0))

        pics = []
        if id > 0:
            pics = self.db.query("SELECT * FROM pics WHERE id>%s and width>0 and height>0 ORDER BY id DESC LIMIT %s", id, 30)

        self.write({'pics':pics})

class install(BaseHandler):
    """docstring for install"""
    
    def get(self):
        return
        sql = """
DROP TABLE IF EXISTS `pics`;
CREATE TABLE IF NOT EXISTS `pics` (
  `id` int(8) unsigned NOT NULL AUTO_INCREMENT,
  `unique_id` varchar(128) NOT NULL,
  `url` varchar(256) NOT NULL,
  `source_url` varchar(256) NOT NULL,
  `width` int NOT NULL,
  `height` int NOT NULL,
  `filesize` FLOAT NOT NULL DEFAULT  '0',
  `from` varchar(10) NOT NULL DEFAULT 'jandan',
  `category` varchar(10) NOT NULL DEFAULT 'default',
  `add_time` int(10) unsigned NOT NULL DEFAULT '0',
  `desc` mediumtext NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_id` (`unique_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8 AUTO_INCREMENT=1;"""

        self.db.execute(sql)
        self.write("ok")

class fetch_jandan(BaseHandler):

    def get(self, page=None):

        if page is not None:
            url = "http://jandan.net/pic/page-%s" % page
        else:
            url = "http://jandan.net/pic"

        req = urllib2.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.47 Safari/536.11')
        response = urllib2.urlopen(req)
        the_page = response.read()

        soup = BeautifulSoup(the_page)

        if page is None:

            current_page = soup.find('span', {"class":"current-comment-page"})
            current_page = current_page.text[1:-1]

            if current_page:
                current_page = int(current_page)

            mc = pylibmc.Client()
                
            #如果没有页码则检索所有页面
            if not mc.get('jandan_current_page'):

                # for i in range(1, current_page+1):
                    # add_task('fetch', '/fetch_jandan/%s' % i)

                mc.set("jandan_current_page", current_page)
                return
            #如果换页了要检索上一页
            elif int(mc.get("jandan_current_page")) < current_page:
                add_task('fetch', '/fetch_jandan/%s' % (current_page-1))

            mc.set("jandan_current_page", current_page)
        else:
            current_page = page

        pics = []
        for comment in list(soup.findAll('li', attrs={'id' : re.compile("^comment")})):

            images = list(comment.findAll('img'))

            if len(images) < 2:
                continue

            pic = {}

            unique_id = comment['id']
            pic['unique_id'] = hashlib.sha1(unique_id).hexdigest()
            pic['url'] = images[1]['src']

            text = []
            for p in list(comment.findAll("p")):

                for img in list(p.findAll("img")):
                    img.extract()

                text.append(p.text)

            pic['desc']       = ''.join(text)
            pic['add_time']   = time.time()
            pic['source_url'] = "http://jandan.net/pic/page-%s#%s" % (current_page, unique_id)

            old_pic = self.db.get("SELECT * FROM pics WHERE unique_id='%s'" % pic['unique_id'])

            #已存在跳过
            if old_pic:
                continue

            pics.append(pic)

        pics.reverse()

        for pic in pics:

            sql = """INSERT INTO pics (unique_id, url, width, height, source_url, `from`, `desc`, add_time)
                 VALUES('%(unique_id)s','%(url)s', '0', '0', '%(source_url)s', 'jandan','%(desc)s', '%(add_time)s')""" % pic

            row_id = self.db.execute(sql)

            if row_id:
                payload = "id=%(id)s&url=%(url)s" % {'id':row_id, 'url':pic['url']}
                add_task('download_image', '/download_image', payload)

        soup = None

        self.write("fetched %s images" % len(pics))

    def post(self,page=None):
        self.get(page)

class download_image(BaseHandler):
    """docstring for download_image"""
    
    def post(self):

        url = self.get_argument("url", None)
        id  = self.get_argument("id", None)

        if not url or not id:
            return
        
        req = urllib2.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.47 Safari/536.11')
        response = urllib2.urlopen(req)
        the_image = response.read()

        imagefile = StringIO(the_image)
        image = Image.open(imagefile)

        if not image:
            return False
                
        source_width, source_height = image.size

        sql = """UPDATE pics SET width='%s',height='%s' WHERE id='%s'""" % (source_width, source_height, id)
        self.db.execute(sql)

        imagefile = None

        self.write("ok")

        