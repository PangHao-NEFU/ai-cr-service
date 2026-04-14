# TypeScript 代码规范

## 代码风格
- 使用 ESLint + Prettier 格式化
- 使用 2 空格缩进
- 每行不超过 100 字符
- 使用分号结尾

## 类型定义
- 禁止使用 `any`，使用 `unknown` 替代
- 优先使用 `interface` 定义对象类型
- 使用类型推断，避免冗余类型声明

```typescript
// 推荐
interface User {
  id: number;
  name: string;
}

// 不推荐
const user: any = fetchData();
```

## 命名规范
- 变量和函数：`camelCase`（例：`getUserById`）
- 类名、接口、类型：`PascalCase`（例：`UserService`）
- 常量：`UPPER_SNAKE_CASE`（例：`API_BASE_URL`）
- 文件名：`kebab-case.ts`

## 函数定义
- 优先使用箭头函数
- 参数和返回值必须有类型注解

```typescript
// 推荐
const getUserById = (id: number): Promise<User> => {
  return api.get(`/users/${id}`);
};

// 不推荐
function getUserById(id) {
  return api.get(`/users/${id}`);
}
```

## 空值处理
- 使用可选链 `?.` 访问可能为空的属性
- 使用空值合并 `??` 提供默认值

```typescript
// 推荐
const name = user?.profile?.name ?? 'Unknown';
```

## 异步处理
- 使用 `async/await` 而非 `.then()`
- 异步函数必须有错误处理

## 模块导入
- 使用 ES Module：`import/export`
- 按需导入，避免 `import *`

## 注释规范
- 使用 JSDoc 注释公共函数
- 复杂类型必须添加说明
