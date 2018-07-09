# django-export-api-doc
auto generate doc from viewset

# Format
```bash
def thisisnone(self, request, *args, **kwargs):
    """接口名字
    Args:
        这里填写请求参数，没有就空一行
        参数: 类型, 描述
    Return:
        这里填写返回参数，没有就空一行
        参数: 类型, 描述
    Example:
        这里填写返回实例，没有就空一行
    """


@list_route(methods=['POST'])
def list(self, request, *args, **kwargs):
    """获取当前用户的所有信息
    Args:
        page_size: int, 每页大小 
        page: int, 页码
    Return:
        permissions: list, 权限
        account_type: str, 账户类型
        last_login: datetime, 上次登录时间
        is_superuser: bool, 是否是超管
        username: str, 用户名
        first_name: str, 昵称
        email: str, 邮箱
        date_joined: datetime, 加入时间
        phone: str, 电话
    Example:
        {
            "code": 0,
            "data": {
                "id": 1,
                "permissions": [],
                "account_type": "超级管理员",
                "last_login": "2018-07-04 07:59:21",
                "is_superuser": true,
                "username": "admin",
                "first_name": "test",
                "last_name": "",
                "email": "zhouting@ww.com",
                "is_staff": true,
                "is_active": true,
                "date_joined": "2018-04-17 07:40:59",
                "person_liable": "",
                "ip_enabled": null,
                "phone": "18013190447",
                "groups": [],
                "user_permissions": []
            }
        }
    """
```

# Usage

- 在Install_App 中添加export_api
- 运行 **python manage.py export_api** 
