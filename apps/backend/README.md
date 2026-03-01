```text
hdap-backend/
├── app/
│   ├── __init__.py           # Flask app 初始化
│   ├── config.py             # 配置文件（数据库、JWT、日志等）
│   ├── extensions.py         # Flask 扩展初始化（SQLAlchemy, JWT, CORS等）
│   ├── models/               # 数据库模型
│   │   ├── __init__.py
│   │   ├── user.py           # 用户表、角色表、权限表
│   │   ├── role.py
│   │   ├── permission.py
│   │   ├── audit.py
│   │   └── ...               # 其他模块模型，如设备、任务等
│   ├── routes/               # 路由层（接口）
│   │   ├── __init__.py
│   │   ├── auth.py           # 登录/登出/注册相关接口
│   │   ├── user.py           # 用户管理接口
│   │   ├── role.py           # 角色管理接口
│   │   ├── permission.py     # 权限接口（查询/分配）
│   │   └── ...               # 其他业务模块接口
│   ├── services/             # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── auth_service.py   # 登录验证、JWT生成
│   │   ├── user_service.py   # 用户增删改查逻辑
│   │   ├── role_service.py
│   │   └── ...               # 其他业务逻辑
│   ├── utils/                # 工具函数
│   │   ├── __init__.py
│   │   ├── security.py       # 密码加密、JWT工具
│   │   ├── decorators.py     # 权限装饰器（@require_permission）
│   │   └── helpers.py
│   └── schemas/              # 数据校验 & 序列化
│       ├── __init__.py
│       ├── user_schema.py
│       └── ...               # 可以用 marshmallow/pydantic
├── migrations/               # 数据库迁移文件（Alembic）
├── tests/                    # 测试用例
│   ├── test_auth.py
│   ├── test_user.py
│   └── ...
├── requirements.txt          # Python依赖
├── run.py                    # 启动 Flask 应用
└── README.md
```