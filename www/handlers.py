from coroweb import get, post, put, delete
from models import User, Blog, Comment, next_id
import logging; logging.basicConfig(level=logging.INFO)
import asyncio
import time
from config import configs
import hashlib
from aiohttp import web
import re
from apis import APIPermissionError, APIValueError, APIResourceNotFoundError, APIError, Page
import json
import markdown2

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


def text2html(text):  # 防止 XSS攻击
    paragraph = text.split('\n')
    paragraph = map(lambda p:p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), paragraph)  # 只表示为文本，不解析为HTML
    return '<br>'.join(paragraph)  # 保留分段吧


def get_model(sql_model):  # 以函数的形式实现类查询
    if sql_model:
        mod = __import__('models')
        for attr in dir(mod):
            if not attr.startswith('_') and (sql_model == (getattr(getattr(mod,attr), '__table__', None) or attr)):
                return getattr(mod,attr)


@asyncio.coroutine
def check_admin(request):
    if not (request.__user__ and request.__user__.admin):
        APIPermissionError('not admin!')



@asyncio.coroutine  # 调用了类的包含异步操作的方法，就要+@修饰器
@get('/')
def index(request, *, index=1):
    index = int(index) if (int(index) > 0) else 1  # 小心传入的不是数字字符串
    item_num = yield from Blog.findNumber('count(id)')
    p = Page(item_num, index, 3)
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset,p.limit))
    blogs = blogs if blogs else ()
    return {
        '__template__':'blogs.html',
        'blogs':blogs,
        'page':p
    }  # return 传参要有'__template__':,'user':,'blogs':  但'GET'方法，没user


@asyncio.coroutine
@get('/blog/{id}')
def get_blog(id):  # 日志内容以及相关的评论等
    blog = yield from Blog.find(id)  # 没找到怎么办：传递id的操作一般为内部操作，很少出现不存在现象
    blog.html_content = markdown2.markdown(blog.content)
    comments = yield from Comment.findAll(where='blog_id=?', args=[id], orderBy='created_at desc')
    if comments:
        for comment in comments:
            comment.html_content = text2html(comment.content)
    return {
        '__template__':'blog.html',
        'blog':blog,
        'comments':comments
    }


@get('/register')
def register(request):
    referer = request.headers.get('referer')  # 传递参数用于返回登录前页面
    return {
        '__template__':'register.html',
        'referer':referer
    }

@get('/signin')
def signin(request):
    referer = request.headers.get('referer')
    return {
        '__template__':'signin.html',
        'referer':referer
    }


@get('/signout')
def signout(request):  # 登录状态的本质是服务器产生或获得确认有效cookie；退出本质是改变客户端持有的原有cookie，验证失效。
    referer = request.headers.get('referer')
    r = web.HTTPFound(referer)
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


@get('/manage/blogs/edit')  # 命名为 删除修改留空间
def create_blog(id=''):
    return {
        '__template__':'edit_blog.html',
        'id':id,  # '001481271773179eea8a2e1a89147e4a1bc88f1ae55ba3c000',
        'action':'/api/blogs'  # 其他传入参数
    }


@get('/manage/{sql_model}')
def manage_blogs(*, sql_model, index=1):
    index = int(index) if (int(index)>0) else 1
    return {
        '__template__':'manage_%s.html' %sql_model,
        'index':index
    }


@asyncio.coroutine
@post('/api/authenticate')
def api_authenticate(request, *, email, passwd):  # 以用户密码验证登录。当然，登录的实质是之后以cookie进入该网站。
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


@asyncio.coroutine
@post('/api/blogs')
def api_edit_blog(request, *, name, summary, content, id=''):
    check_admin(request)  # 验证request.__user__存在，且具有发表blog的资格。
    if not name or not name.strip():
        raise APIValueError('name', 'name should not be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary should not be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content should not be empty.')
    if id:
        blog = yield from Blog.find(id)
        blog.name = name.strip()
        blog.summary = summary.strip()
        blog.content = content.strip()
        yield from blog.update()
        logging.info('Blog "%s:%s" updated.' % (blog.name, blog.id))
    else:
        blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,
                name=name.strip(), summary=summary.strip(), content=content.strip())
        yield from blog.save()
        logging.info('Blog "%s:%s" saved.' % (blog.name, blog.id))
    return blog


@asyncio.coroutine
@post('/api/blogs/{id}/comments')
def api_create_comments(request, *, id, content):
    if not content.strip():
        raise APIValueError('content', 'comment content should not be empty.')
    comment = Comment(blog_id=id, user_id=request.__user__.id, user_name=request.__user__.name,
                      user_image=request.__user__.image, content=content.strip())
    yield from comment.save()
    logging.info('"%s"\'s comment saved. %s' % (comment.user_name, comment.id))
    return comment


@asyncio.coroutine
@get('/api/blogs/{id}')  # 注意这里是get方法！ 请求传递参数只有id
def api_get_blog(*, id):
    blog = yield from Blog.find(id)  # 没有找到怎么办：能传递id一般为内部操作，很少会在这里不存在。
    logging.info('get Blog:%s' % blog.name)
    return blog


@asyncio.coroutine
@get('/api/{sql_model}/{id}/delete')
def api_blogs_delete(request, *, sql_model, id):  # 需要验证权限
    check_admin(request)
    SQLModel = get_model(sql_model)
    if SQLModel is None:
        raise AttributeError
    query_result = yield from SQLModel.find(id)
    if query_result:
        yield from query_result.remove()
        logging.info('%s: \"%s\" removed' % (getattr(SQLModel,'__name__',''), (getattr(query_result,'name',None) or getattr(query_result,'content',None))) )
    return query_result


@asyncio.coroutine
@get('/api/{sql_model}')  # 请求某一页，返回某一页的数据库信息。条目，是否有上下页等。
def api_blogs(request, *, sql_model, index=1):
    check_admin(request)
    SQLModel = get_model(sql_model)  # 新建一个识别models中所有model类的函数
    if SQLModel is None:
        raise AttributeError
    index = int(index) if (int(index) > 0) else 1  # 小心传入的不是数字字符串
    item_num = yield from SQLModel.findNumber('count(id)')
    p = Page(item_num, index, 8)
    query_results = yield from SQLModel.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    query_results = query_results if query_results else () # 如果blogs为None，循环操作会报类型错误
    return {
        'page':p,
        sql_model:query_results
    }







