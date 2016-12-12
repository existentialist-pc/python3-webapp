#数据库操作 类化框架

import logging; logging.basicConfig(level=logging.INFO)
import asyncio,aiomysql


@asyncio.coroutine
def create_pool(loop, **kw): #只创建 global变量 不返回   init 中直接调用！
    logging.info('create database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host = kw.get('host','localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True), #这里就不用定义 conn.commit()
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )

@asyncio.coroutine
def select(sql, args= None, size= None): #查询
    logging.info("SQL:'%s' args:'%s'" % (sql, args or []))
    with (yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor) #字典格式返回
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' % len(rs))
    return rs


@asyncio.coroutine
def execute(sql, args= None, autocommit= True): #传参 autocommit=True 控制 提交方式。
    logging.info("SQL:'%s' args:'%s'" % (sql, args or []))
    with (yield from __pool) as conn:
        if not autocommit:
            yield from conn.begin() #?有这个语法？
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'), args or ())
            affected = cur.rowcount #返回受影响的行数值
            if not autocommit:
                yield from conn.commit()
        except BaseException as e:
            yield from conn.rollback() #不知道有没有这个
            raise e
        yield from cur.close()
    return affected



class Field(object):

    def __init__(self, name, column_type, primary_key,default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return  '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):

    def __init__(self, name = None, ddl = 'varchar(100)', primary_key = False, default = ''):
        super().__init__(name, ddl, primary_key, default)

class IntegerField(Field):

    def __init__(self, name = None, ddl = 'bigint(10)', primary_key = False, default = 0):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):

    def __init__(self, name = None, ddl = 'boolean', default = False):
        super().__init__(name, ddl, False, default)

class FloatField(Field):

    def __init__(self, name = None, ddl = 'real', primary_key = False, default = 0.0):
        super().__init__(name, ddl, primary_key, default)

class TextField(Field):

    def __init__(self, name = None, ddl = 'text', default = ''):
        super().__init__(name, ddl, False, default)

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name # 便于dict中找不到返回None,所以不采用 attrs['__table__']
        logging.info('found model: %s (table: %s)' % (name,tableName))

        mappings = dict()
        fields = list()
        primaryKey = None
        for k,v in attrs.items():
            if isinstance(v, Field):
                logging.info('found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field：%s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f:'`%s`' % f, fields))
        # 疯狂新建属性
        attrs['__mappings__'] = mappings
        attrs['__table__'] = tableName  # 这个防止有没定义的用实例类名
        attrs['__primary_key__'] = primaryKey  # 用的key而不是v.name
        attrs['__fields__'] = fields  # 这段以后可以修改：把primaryKey添加进去保证在最后一位。由于没添加pk，导致下面有的代码写的有点难看，要单独考虑pk
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句: 关于主key的
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ','.join(list(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields))), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s, ?)' % (tableName, ', '.join(escaped_fields), primaryKey, ', '.join(list(map(lambda f: '?', fields))))
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass= ModelMetaclass):

    def __init__(self, **kw):
        super().__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):  # 没有传递值的时候，Field中的default就起到传入默认值的作用。
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s：%s' % (key,str(value))) #防止value是 迭代类型？
                setattr(self, key, value)
        return value

    @classmethod
    @asyncio.coroutine
    def find(cls, pk): # 找到主键pk对应key输出的结果
        """ find object by primary key. """
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])  # 把字典变为 a=b,c=d 格式。dict默认显示

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where= None, args= None):  # 找到select count(*) from 表名输出的结果
        """ find quantity of search result by select and where. selectField 要输出的列 where判断语句 arg：where中?替换的值 """
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1) #注意，没where就没args
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    @asyncio.coroutine
    def findAll(cls, where= None, args= None, **kw):
        """ find objects by where clause. 输出多个结果。 **kw为附加 orderBy limit等 SQL命令"""
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        if args is None:  #为什么要limit作为参 传参进sql语句，而不是直接加上？ 为了语句的通用性？
            args = []
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit,tuple):
                sql.append('?,?')
                args.extend(limit)  #要用extend！！
            else:
                raise ValueError('Invalid limit value: %s' % str(limit)) #防止limit是tuple出错
        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]  # 如果 rs为[]则 该值也返回[],不能加None判断，如果加，后续len(None)python会报错。

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))  #此时会对新建默认值
        args.append(self.getValueOrDefault(self.__primary_key__))
        rs = yield from execute(self.__insert__, args)
        if rs != 1:
            logging.info('failed to insert record: affected rows: %s' % rs)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))  # 为了防止出现匹配不成功，此处不能随意创建默认值
        args.append(self.getValue(self.__primary_key__))
        rs = yield from execute(self.__update__, args)
        if rs != 1:
            logging.info('failed to update by primary key: affected rows: %s' % rs)

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rs = yield from execute(self.__delete__, args)
        if rs != 1:
            logging.info('failed to remove by primary key: affected rows: %s' % rs)
