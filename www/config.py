import config_default

class Dict(dict):

    def __init__(self, names=(), values=(), **kw):
        super().__init__(**kw)
        for k,v in zip(names, values): #这个names values 视为了自定义dict传参？ zip实现 n个可迭代 第0，1，2...个元素分别打包
            self[k] = v

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)


def merge(default, override): #内部方法所以不做 传参数类型try except处理？
    rs = {}
    for k, v in default.items():
        if k in override:
            rs[k] = merge(v, override[k]) if isinstance(v, dict) else override[k]
        else:
            rs[k] = v
    return rs

def toDict(d):
    D = Dict()
    for k, v in d.items():
        D[k] = toDict(v) if isinstance(v,dict) else v
    return D

configs = config_default.configs

try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)
