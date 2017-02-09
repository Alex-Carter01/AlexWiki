import webapp2
import logging
import re
import cgi
import jinja2
import os
import random
import string
import hashlib
import hmac
import Cookie 
import urllib2
import time
from datetime import datetime, timedelta
from google.appengine.api import memcache
from google.appengine.ext import db
from xml.dom import minidom

DEFAULT = "This page is blank, please edit it"

tool_logd = """
 <a class="tool-link" href="/">home </a>|
 <a class="tool-link" href="/logout">logout</a>
 """

tool_nonlog = """
  <a class="tool-link" href="/">home </a>|
  <a class="tool-link" href="/login">login </a>|
  <a class="tool-link" href="/signup">signup</a>
"""

## see http://jinja.pocoo.org/docs/api/#autoescaping
def guess_autoescape(template_name):
   if template_name is None or '.' not in template_name:
      return False
      ext = template_name.rsplit('.', 1)[1]
      return ext in ('html', 'htm', 'xml')

JINJA_ENVIRONMENT = jinja2.Environment(
   autoescape=guess_autoescape,     ## see http://jinja.pocoo.org/docs/api/#autoescaping
   loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
   extensions=['jinja2.ext.autoescape'])

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")  # 3-20 characters (a-zA-Z0-9_-)
def valid_username(username):
   return USER_RE.match(username)

PASSWORD_RE = re.compile(r"^.{3,20}$")          # 3-20 characters (any)
def valid_password(username):
   return PASSWORD_RE.match(username)

EMAIL_RE = re.compile(r"^[\S]+@[\S]+\.[\S]+$")
def valid_email(username):
   return EMAIL_RE.match(username)

class WikiHandler(webapp2.RequestHandler):
   def write(self, *items):    
      self.response.write(" : ".join(items))

   def render_str(self, template, **params):
      tplt = JINJA_ENVIRONMENT.get_template('templates/'+template)
      return tplt.render(params)

   def render(self, template, **kw):
      self.write(self.render_str(template, **kw))

   def render_json(self, d):
      json_txt = json.dumps(d)
      self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
      self.write(json_txt)

def valid_url(url):
    logging.info("*** regex match: "+str(bool(WEBSITE_REGEX.match(url))))
    return bool(WEBSITE_REGEX.match(url))

def make_salt():
   return ''.join(random.choice(string.hexdigits) for _ in range(25))

def make_pw_hash(name, pw, salt=None):
   if not salt:
      salt = make_salt()
   return hashlib.sha256(name+pw+salt).hexdigest()+'|'+salt

def valid_pw(name, pw, h):
   salt = h.split('|')[1]
   return h == make_pw_hash(name, pw, salt)

SECRET="mr2K9yS0n1QuNJTbKAmb6P9QPcQ7NbceO6ei8"
def hash_str(s):
   return hmac.new(SECRET,s).hexdigest()

def make_secure_val(s):
   return s+'|'+hash_str(s)

def check_secure_val(h):
   val = h.split('|')[0]
   if (h == make_secure_val(val)):
      return val

def username_from_cookie(cookie):
  if cookie:
    user_id = check_secure_val(cookie)
    if user_id:
       user = MyUsers.get_by_id(int(user_id))
       return user.username

def check_login_handler(self):
   cook = self.request.cookies.get('user_id','0')
   if check_secure_val(cook):
      #user is logged in
      us_id = cook.split('|')[0]
      logging.info("us-id: "+us_id)
      user = MyUsers.get_by_id(int(us_id)).username
      logging.info("user's name:" + str(user))
      return user
   else:
      #user is not logged in
      self.redirect('/')
      return False

def soft_login_handler(self):
   cook = self.request.cookies.get('user_id','0')
   if cook != "":
      #user is logged in
      us_id = cook.split('|')[0]
      logging.info("us-id: "+us_id)
      user = MyUsers.get_by_id(int(us_id)).username
      logging.info("user's name:" + str(user))
      return user
   else:
      #user is not logged in
      return False

def user_login_handler(self):
   cook = self.request.cookies.get('user_id','0')
   if check_secure_val(cook):
      #user is logged in
      us_id = cook.split('|')[0]
      logging.info("us-id: "+us_id)
      user = MyUsers.get_by_id(int(us_id)).username
      logging.info("user's name:" + str(user))
      self.redirect("/")
   else:
      #user is not logged in
      return False

def age_str(age):
   s = 'cache age: %ss'
   return s % age

def update_cache(pagename):
  logging.info("memcache updating at specific key")
  #posts = db.GqlQuery("SELECT * FROM WikiPages ORDER BY created")
  #temp = list(posts)
  mc_set(pagename, temp)

def clear_cookie(self):
  logging.info("logging user out")
  self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

def full_update_cache():
  logging.info("updating the entire memcache")
  posts = db.GqlQuery("SELECT * FROM WikiPages ORDER BY created")
  temp = list(posts)
  for post in temp:
    mc_set(post.title, post.content)

def mc_set(key, val):
  time = datetime.utcnow()
  tup = (val, time)
  memcache.set(key, tup)
  return None

def mc_get(key):
  global DEFAULT
  if memcache.get(key):
    now = datetime.utcnow()
    then = memcache.get(key)[1]
    dif = now - then
    age = timedelta.total_seconds(dif)
    #age = 14
    logging.info("**** age:"+str(age))
    value = memcache.get(key)
    tup = (value[0], age)
    return tup 
  else:
    logging.info("oops, key not found in memcache")
    tup = (DEFAULT, 0)
    return tup

class MyUsers(db.Model):
   username   = db.StringProperty()   
   pwhashsalt = db.StringProperty()
   email      = db.StringProperty()
   created    = db.DateTimeProperty(auto_now_add = True)

class WikiPages(db.Model):
   title = db.StringProperty()
   content = db.TextProperty()
   last_edited = db.StringProperty()
   created    = db.DateTimeProperty(auto_now_add = True)

class Signup(WikiHandler):
   def get(self):
      logging.info("********** SignUp GET **********")
      user_login_handler(self)
      self.render("signup.html", tool_logd=tool_logd, tool_nonlog=tool_nonlog)

   def post(self):
      user_login_handler(self)
      user_username = self.request.get('username')
      user_password = self.request.get('password')
      user_verify   = self.request.get('verify')
      user_email    = self.request.get('email')

      user_username_v = valid_username(user_username)
      user_password_v = valid_password(user_password)
      user_verify_v   = valid_password(user_verify)
      user_email_v    = valid_email(user_email)

      username_error_msg = password_error_msg = verify_error_msg = email_error_msg = ""
      if not(user_username_v):
         username_error_msg = "That's not a valid username."

      if (user_password != user_verify):
         password_error_msg = "Passwords do not match."
      elif not(user_password_v):
         password_error_msg = "That's not a valid password."
         if (user_email != "") and not(user_email_v):
            email_error_msg = "That's not a valid email."

      userQuery = db.GqlQuery("SELECT * FROM MyUsers WHERE username = '%s'" % user_username)
      if not(userQuery.count() == 0 or userQuery.count() == 1): 
         logging.info("***DBerr(signup) username = " + user_username + " (count = " + str(userQuery.count()) + ")" )
      user = userQuery.get() ## .get() returns Null if no results are found for the database query

      if user and user.username == user_username:
         user_username_v = False
         username_error_msg = "That user already exists."

      logging.info("DBG: The inputs="      \
                   +user_username + " " \
                   +user_password + " " \
                   +user_verify   + " " \
                   +user_email)

      logging.info("DBG: The valids="+str(bool(user_username_v))+" " \
                   +str(bool(user_password_v))+" " \
                   +str(bool(user_verify_v))  +" " \
                   +str(bool(user_email_v)))


      if not(user_username_v and user_password_v and user_verify_v and ((user_email == "") or user_email_v) and (user_password == user_verify)):
         template_values = {'error_username': username_error_msg,
                            'error_password': password_error_msg,
                            'error_verify'  : verify_error_msg,
                            'error_email'   : email_error_msg,
                            'username_value': user_username,
                            'email_value'   : user_email,
                            'username' : user, 
                            'tool_logd' : tool_logd,
                            'tool_nonlog' : tool_nonlog}
         self.render("signup.html", **template_values)
      else:
         pw_hash = make_pw_hash(user_username, user_password)
         u = MyUsers(username=user_username, pwhashsalt=pw_hash, email=user_email)
         u.put()
         id = u.key().id()
         self.response.headers.add_header('Set-Cookie', 'user_id=%s; max-age=604800; Path=/' % make_secure_val(str(id)))
         self.redirect("/")

class Login(WikiHandler):
   def get(self):
      logging.info("********** LogIn GET **********")
      user_login_handler(self)
      self.render("login.html",error="", tool_logd=tool_logd, tool_nonlog=tool_nonlog)

   def post(self):
      logging.info("DBG: Login POST")
      user_login_handler(self)
      user_username = self.request.get('username')
      user_password = self.request.get('password')

      users = db.GqlQuery("SELECT * FROM MyUsers ")
      users = list(users)    # save posts in a list to avoid doing DB queries whereever posts is used

      ## NOTE: make sure that username is a db.StringProperty() and not db.TextProperty
      userQuery = db.GqlQuery("SELECT * FROM MyUsers WHERE username = '%s'" % user_username)
      if userQuery.count() != 1:
         logging.info("***DBerr (login) username = " + user_username + " (count = " + str(userQuery.count()) + ")" )
      user = userQuery.get() ## .get() returns Null if no results are found for the database query

      if user and user.username == user_username and valid_pw(user_username,user_password,user.pwhashsalt):
         id = user.key().id()
         self.response.headers.add_header('Set-Cookie', 'user_id=%s; max-age=604800; Path=/' % make_secure_val(str(id)))
         self.redirect("/")
      else:
         self.render("login.html",error="Invalid login", username = user, tool_logd=tool_logd, tool_nonlog=tool_nonlog)
         
class Logout(WikiHandler):
   def get(self):
      clear_cookie(self)
      #self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')
      #self.response.write("<script type=\"text/javascript\">window.history.back();</script><noscript>Please enable javascript you heathen.</noscript>")
      self.redirect('/')

class Flush(WikiHandler):
   def get(self):
    logging.info("flushing memcache")
    memcache.flush_all()
    self.redirect("/")

class Delete(WikiHandler):
   def get(self):
    logging.info("deleting database")
    clear_cookie(self)
    dbQuery = db.GqlQuery("SELECT * FROM WikiPages ")
    results = list(dbQuery)
    for result in results:
      result.delete()
    logging.info("deleting users")
    dbQuery1 = db.GqlQuery("SELECT * FROM MyUsers ")
    results1 = list(dbQuery1)
    for resulty in results1:
      resulty.delete()
    self.redirect("/")

class EditPage(WikiHandler):
   def get(self, pagename):
      global DEFAULT
      user = check_login_handler(self)
      current = ""
      body = mc_get(pagename) #cache
      if body[0] != DEFAULT:
        memcache = "*"
      else:
        "page is empty in memcache, refreshing"
        full_update_cache()
        body = mc_get(pagename)
      time = age_str(body[1])
      logging.info("body: "+str(body[0]))
      body = str(body[0])
      current = """"""+body
      self.render("editpage.html", name=pagename, username = user, tool_logd=tool_logd, tool_nonlog=tool_nonlog, current=current)
      #self.response.write("<script type=\"text/javascript\">window.history.back();</script><noscript>Please enable javascript you heathen.</noscript>")

   def post(self, pagename):
      user = check_login_handler(self)
      logging.info("proccessing user's edits")
      edit = self.request.get("edit")
      page = WikiPages(title=pagename, content=edit, last_edited=user)
      page.put()
      time.sleep(0.1)
      full_update_cache()
      self.redirect(pagename)
      #this user should update memcache

class HistoryPage(WikiHandler):
   def get(self, pagename):
    global DEFAULT
    user = check_login_handler(self)
    logging.info("viewing page history, includes DB access")
    posts = db.GqlQuery("SELECT * FROM WikiPages WHERE title = '%s' ORDER BY created" %pagename) 
    temp = list(posts)
    self.render("history.html", name=pagename, username=user, tool_logd=tool_logd, tool_nonlog=tool_nonlog, history=temp) 

    def post(self, pagename):
      logging.info("this is gonna be rough")
	  edit = self.request.get("edit")#redirect to /_edit with the correct pointer
	  view = self.request.get("view")#not sure what to do// new archive  /_archive?
	  

class WikiPage(WikiHandler):
   def get(self, pagename):
      global DEFAULT
      user = soft_login_handler(self)
      memcache = "" #change to reflect if website was loded from cache
      body = mc_get(pagename) #cache
      if body[0] != DEFAULT:
        memcache = "*"
      else:
        "page is empty in memcache, refreshing"
        full_update_cache()
        body = mc_get(pagename)
      time = age_str(body[1])
      logging.info("body: "+str(body[0]))
      body = str(body[0])
      if not user:
        if body == DEFAULT:
          self.redirect("/")
      self.render("wikipage.html", name=pagename, username = user, tool_logd=tool_logd, tool_nonlog=tool_nonlog, memcache=memcache, body=body, time=time)

class MainPage(WikiHandler):
   def get(self):
      user = soft_login_handler(self)
      self.render("main.html", username = user, tool_logd=tool_logd, tool_nonlog=tool_nonlog)   

## (?: ) is a non-capturing group - see http://stackoverflow.com/questions/3512471/non-capturing-group      
PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'  ## anything in parenthesis is passed as a parameter to WikiPage or EditPage get()

application = webapp2.WSGIApplication([
                               ('/', MainPage),
                               (r'/signup/?', Signup),
                               (r'/login/?', Login),
                               (r'/logout/?', Logout),
                               (r'/flush/?', Flush),
                               (r'/delete/?', Delete),
                               ('/_edit' + PAGE_RE, EditPage),
                               ('/_history' + PAGE_RE, HistoryPage),
                               (PAGE_RE, WikiPage),  
                               ],
                              debug=True)
