#!/usr/bin/env python3.5
#
#起到__init__函数的作用。
import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

from jinja2 import Environment, FileSystemLoader

import orm  #数据库操作
from coroweb import add_routes, add_static

from config_default import configs

def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        autoescape = kw.get('autoescape', True),
        auto_reload = kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    env = Environment(loader= FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    logging.info('set jinja2 template path: %s' % path )
    app['__templating__'] = env

@asyncio.coroutine
def logger_factory(app, handler):
    @asyncio.coroutine
    def logger(request): #类似于 装饰器， 用logger把handler包装。
        logging.info('Response: %s:%s' % (request.method, request.path))
        return (yield from handler(request))
    return logger

@asyncio.coroutine
def data_factory(app, handler):
    @asyncio.coroutine
    def parse_data(request):
        request.__data__ = dict()
        if request.method in ('POST', 'PUT'):
            if not request.content_type:
                return web.HTTPBadRequest('Missing Content-Type.')
            content_type = request.content_type.lower()
            if content_type.startwith('application/json'):
                request.__data__= yield from request.json()
                if not isinstance(request.__data__, dict):
                    return web.HTTPBadRequest('JSON body must be object.')
                logging.info('request json: %s' % request.__data__)
            elif content_type.startwith(('application/x-wwW-form-urlencoded', 'multipart/form-data')):
                request.__data = yield from dict(**request.post())
                logging.info('request form: %s' % request.__data__)
            else:
                return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
        if request.method == 'GET':
            qs = request.query_string
            if qs:
                for k, v in urllib.parse.parse_qs(qs, True):  # v是list类型
                    request.__data__[k] = v[0]
                logging.info('request query: %s' % request.__data__)
        return (yield from handler(request))
    return parse_data

@asyncio.coroutine
def response_factory(app, handler):
    @asyncio.coroutine
    def response(request):
        logging.info('Response handler...')
        rs = yield from handler(request)
        logging.info(type(rs)) # 页面异常时调试使用
        if isinstance(rs, web.StreamResponse): #包装好的web.数据类型 直接返回数据内容
            return rs
        if isinstance(rs, bytes):
            resp = web.Response(body = rs)
            resp.content_type = 'application/octent-stream'
            return resp
        if isinstance(rs, str):
            if rs.startswith('redirect:'):
                return web.HTTPFound(rs[9:])
            resp = web.Response(body = rs.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(rs, dict):
            template = rs.get('__template__') #结果是否包含 __template__ 项
            if template is None:
                resp = web.Response(body = json.dumps(rs, ensure_ascii= True, default= lambda o:o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset= utf-8'
                return resp
            else: #调用template模板
                resp = web.Response(body = app['__templating__'].get_template(template).render(**rs).encode('utf-8'))
                resp.content_type= 'text/html;charset=utf-8'
                return resp
        if isinstance(rs, int) and 100<= rs<=600:
            return web.Response(status = rs) #返回状态 数字码
        if isinstance(rs, tuple) and len(rs)==2:
            status, message = rs
            if isinstance(status, int) and 100<= status<=600:
                resp = web.Response(status = status, text = str(message))
                return resp
        resp = web.Response(body = str(rs).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response


def datetime_filter(t): #把整数时间解析成日常可接受形态
    delta = int(time.time()-t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta//60)
    if delta < 86400:
        return u'%s小时前' % (delta//3600)
    if delta < 604800:
        return u'%s天前' % (delta//86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' %(dt.year, dt.month, dt.day)

def index(request):
    rs = web.Response(body=b'<h1>Awesome,man</h1>')

    print(isinstance(rs, web.StreamResponse)) # 包装好的web.数据类型 直接返回数据内容
    print(rs)
    print(type(rs))
    return rs

@asyncio.coroutine
def init(loop):
    yield from orm.create_pool(loop=loop ,**configs['db'])
    #核心是执行 yield from aiomysql.create_pool()
    app = web.Application(loop=loop, middlewares=[logger_factory, response_factory])
    init_jinja2(app, filters=dict(datetime= datetime_filter))
    #app.router.add_route('GET','/',index)
    add_routes(app,'handlers')
    add_static(app)
    srv = yield from loop.create_server(app.make_handler(),'127.0.0.1',9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()