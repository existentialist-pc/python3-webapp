from coroweb import get, post, put, delete
from models import User, Blog, Comment, next_id
import logging; logging.basicConfig(level=logging.INFO)
import asyncio
import time
from config import configs
import hashlib
from aiohttp import web
import re
from apis import APIValueError, APIResourceNotFoundError, APIError
import json

'''

@asyncio.coroutine
@get('/')
def index(request):
    users = yield from User.findAll()
    return {
        '__template__': 'blogs.html',
        'user': users[0],
    }
'''

COOKIE_NAME = 'session'
_COOKIE_KEY = configs.session.secret

_RE_EMAIL = re.compile(r'^[0-9a-z\.\-\_]+\@[0-9a-z\-\_]+(\.[0-9a-z\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

def user2cookie(user, max_age):
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)  # id-密码-时效-服务器保密参数
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)  # passwd为用户输入值，JS检验email:password后sha1，再POST进python与id:passwd后sha1，最后得到的值传入sql。

@asyncio.coroutine
def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():  # 验证时效！别总忘了类型转换。
            return None
        user = yield from User.find(uid)
        if not user:
            return None
        s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:  # 控制环节错误，如异步回调
        logging.exception(e)
        return None



#@asyncio.coroutine # 调用了类的包含异步操作的方法，就要+@修饰器
@get('/')
def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Something Useful', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='中文博客', summary=summary, created_at=time.time()-72000)
    ] # name, create_at, summary
    #blogs = yield from Blog.findAll()
    #logging.info('执行了吗?')
    return {
        '__template__':'blogs.html',
        'blogs':blogs
    }#  return 传参要有'__template__':,'user':,'blogs':  但'GET'方法，没user

@get('/register')
def register(request):
    return {
        '__template__':'register.html'
    }

@get('/signin')
def signin(request):
    return  {
        '__template__':'signin.html'
    }

@get('/signout')
def signout(request):  # 登录状态的本质是服务器产生或获得确认有效cookie；退出本质是改变客户端持有的原有cookie，验证失效。
    referer = request.headers.get('referer')
    r = web.HTTPFound(referer)
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@asyncio.coroutine
@post('/api/authenticate')
def api_authenticate(*, email, passwd):  # 以用户密码验证登录。当然，登录的实质是之后以cookie进入该网站。
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email', 'Invalid email.')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd', 'Invalid password.')
    users = yield from User.findAll('email=?', [email])
    if len(users) != 1:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    sha1_testpwd = '%s:%s' % (user.id, passwd)
    if user.passwd != hashlib.sha1(sha1_testpwd.encode('utf-8')).hexdigest():
        raise APIValueError('passwd', 'Invalid password.')

    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@asyncio.coroutine
@post('/api/users')
def api_register_user(*, email, name, passwd):  # 要记得email要从原始获得值.lower()转换。
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = yield from User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register: failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save()

    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r