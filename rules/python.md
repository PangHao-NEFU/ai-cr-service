# Python 代码规范

## 代码风格
- 遵循 PEP 8 规范
- 使用 4 空格缩进，禁止 Tab
- 每行不超过 120 字符
- 文件使用 UTF-8 编码，文件头不需要声明

## 命名规范
- 变量和函数：`snake_case`（例：`get_user_by_id`）
- 类名：`PascalCase`（例：`UserService`）
- 常量：`UPPER_SNAKE_CASE`（例：`MAX_RETRY_COUNT`）
- 私有属性/方法：前缀下划线（例：`_internal_cache`）

## 类型注解
- 公共函数必须有类型注解
- 使用 `typing` 模块的类型（例：`List[str]`, `Optional[int]`）

```python
# 推荐
def get_user(user_id: int) -> Optional[User]:
    ...

# 不推荐
def get_user(user_id):
    ...
```

## 异常处理
- 禁止裸 `except:`，必须指定异常类型
- 异常信息要有意义，便于定位问题

```python
# 推荐
try:
    result = do_something()
except ValueError as e:
    logger.error(f"参数错误: {e}")
    raise

# 不推荐
try:
    result = do_something()
except:
    pass
```

## 资源管理
- 使用 `with` 语句管理资源（文件、数据库连接等）
- 使用 `contextlib` 管理上下文

## 导入规范
- 标准库 → 第三方库 → 本地模块，用空行分隔
- 禁止使用 `from module import *`

## 文档字符串
- 公共函数和类必须有 docstring
- 使用 Google 风格或 NumPy 风格
