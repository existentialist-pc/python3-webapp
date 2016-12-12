import logging

class Page():  # 思考函数的类化

    def __init__(self, item_num, page_index=1, items_per_page=10):
        self.item_num = item_num
        self.items_per_page = items_per_page
        self.page_index = page_index if (page_index >= 1) else 1
        self.page_num = item_num // items_per_page + (1 if (item_num % items_per_page) else 0)
        if (self.page_index <= self.page_num):
            self.offset = (self.page_index - 1) * self.items_per_page
            self.limit = self.items_per_page
        else:
            self.offset = 0
            self.limit = 0
        self.has_next = self.page_num > self.page_index
        self.has_previous = self.page_index > 1

    def __str__(self):
        return ('item_num:%s, page_num:%s, page_index:%s, items_per_page:%s, offset:%s, limit:%s' %
                (self.item_num, self.page_num, self.page_index, self.items_per_page, self.offset, self.limit))

    __repr__ = __str__

class APIError(Exception):

    def __init__(self, error, data='', message=''):
        super().__init__(message)
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):

    def __init__(self, field, message=''):
        super().__init__('value: invalid', field, message)

class APIResourceNotFoundError(APIError):

    def __init__(self, field, message=''):
        super().__init__('value: notfound', field, message)

class APIPermissionError(APIError):

    def __init__(self, message=''):
        super().__init__('permission: forbidden', 'permission', message)

