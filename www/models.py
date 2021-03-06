# 数据库 实例类

import time, uuid
from orm import Model, StringField, IntegerField, BooleanField, FloatField, TextField


def next_id():
    return '%015d%s000' % (int(time.time()*1000), uuid.uuid4().hex)  # %015d 15位整数不足用0填充 return凑齐50位字符串，十六进制数


class User(Model):  # 类对象

    __table__ = 'users'

    id = StringField(ddl = 'varchar(50)', primary_key = True, default = next_id)
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField(default = False)
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)  # 保存到数据库的时候调用。save函数内的getValueOrDefault内 会执行default()。


class Blog(Model):

    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)


class Comment(Model):

    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)