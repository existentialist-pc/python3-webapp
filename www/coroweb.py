# 整合web框架，解析url及request参数，提取返回页面函数需要的参数。
import os
import inspect
import functools
import logging
import urllib.parse
import asyncio
from aiohttp import web
#from apis import APIError

def request_type(method):  #用工厂模式，生成GET、POST等请求方法的装饰器
    def _request(path):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args,**kwargs):
                return func(*args,**kwargs)
            wrapper.__method__ = method
            wrapper.__route__ = path
            return wrapper
        return decorator
    return _request

get = request_type('GET')
post = request_type('POST')
put = request_type('PUT')
delete = request_type('DELETE')

class RequestHandler:

    def __init__(self, app, fn):
        self._app = app
        self._fn = asyncio.coroutine(fn) #疑问，fn = asyncio.coroutine(fn) 可以放在这里吗？可以哈。

    @asyncio.coroutine
    def __call__(self, request):

        req_kw = dict()
        if request.method in ('POST', 'PUT'):
            if not request.content_type:
                return web.HTTPBadRequest('Missing Content-Type.')
            content_type = request.content_type.lower()
            if content_type.startswith('application/json'):
                req_kw = yield from request.json()
                if not isinstance(req_kw, dict):
                    return web.HTTPBadRequest('JSON body must be object.')
            elif content_type.startswith(('application/x-wwW-form-urlencoded','multipart/form-data')):
                req_kw = yield from dict(**request.post())
            else:
                return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
        if request.method == 'GET':
            qs = request.query_string
            if qs:
                for k, v in urllib.parse.parse_qs(qs,True).items(): #v是list类型
                    req_kw[k] = v[0]

        #是否有特殊传参数
        if request.match_info:  #如果和以上有相同的key会更新。
            req_kw.update(request.match_info)
        req_kw['request'] = request

        #根据需要传参
        required_args = inspect.signature(self._fn).parameters
        kw = {arg: value for arg, value in req_kw.items() if arg in required_args}

        #判断是否有未传参数
        for k, v in required_args.items():
            if k == 'request' and v.kind in (v.VAR_POSITIONAL, v.VAR_KEYWORD):
                return web.HTTPBadRequest('requst parameter cannot be the var argument')
            if (v.default == v.empty) and (k not in kw) and (v.kind not in (v.VAR_POSTIONAL, v.VAR_KEYWORD)):
                return web.HTTPBadRequest('missing argument: %s' % k)
        logging.info('call with args:%s' % str(kw))

        try:
            rs = yield from self._fn(**kw)  # 这里执行handlers，获得结果返回
            return rs
        except:# APIError as e:
            return 0 #dict(error = e.error, data = e.data, message = e.message)

def add_routes(app, module_name): #把所有的路由处理函数和地址联系起来。所以需要__import__。（需要装载的moodule位置 ）
    ''' #该方法核心思想：如果不是A.B格式，直接读该文件；如果是A.B则__import__一定要包含fromlist！保证引入name成功。然后引入调用到最后的B文件
    n = module_name.rfind('.')
    if n = -1:
        mod = __import__(module_name)
    else:
        sub_name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n],fromlist=[sub_name]),sub_name, -1)
        if mod == -1:
            return web.HTTPBadRequest('module %s:%s not found!' % (module_name, sub_name))
    '''
    mod = __import__(module_name,fromlist=['this_is_for_valid_import_module_name'])
    for attr in dir(mod): #dir(mod)只获得mod的属性方法等字符串名字list，不获得方法本身！
        if not attr.startswith('_'):
            fn = getattr(mod, attr)  #获得方法本身
            if callable(fn) and hasattr(fn, '__method__') and hasattr(fn, '__method__'):
                method = getattr(fn, '__method__', None) #不要使用 fn.__method__暴力调用！
                path = getattr(fn, '__route__', None)
                app.router.add_route(method, path, RequestHandler(app,fn))
                args = ','.join(inspect.signature(fn).parameters.keys())
                logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, args))

def add_static(app): #不传需要的参数,以本文件路径 为基准 找到 static配置文件位置。
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static') #根据该文件位置修改。 getcwd()不能传参！
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))





