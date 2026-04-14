# Java 代码规范

## 代码风格
- 遵循 Google Java Style 或阿里巴巴 Java 开发手册
- 使用 4 空格缩进
- 每行不超过 120 字符

## 命名规范
- 类名：`PascalCase`（例：`UserService`）
- 方法名和变量：`camelCase`（例：`getUserById`）
- 常量：`UPPER_SNAKE_CASE`（例：`MAX_RETRY_COUNT`）
- 包名：全小写（例：`com.company.service`）

## 空值处理
- 使用 `Optional` 包装可能为空的返回值
- 禁止传递 `null` 参数，考虑使用空对象模式
- 使用 `@NonNull` 和 `@Nullable` 注解标注

```java
// 推荐
public Optional<User> findById(Long id) {
    return userRepository.findById(id);
}

// 不推荐
public User findById(Long id) {
    return userRepository.findById(id); // 可能返回 null
}
```

## 异常处理
- 禁止捕获后不处理（空 catch 块）
- 使用 try-with-resources 管理资源
- 受检异常应慎用，优先使用运行时异常

```java
// 推荐
try (BufferedReader reader = new BufferedReader(new FileReader(path))) {
    return reader.readLine();
}

// 不推荐
try {
    // ...
} catch (Exception e) {
    // 空处理
}
```

## 集合使用
- 使用泛型，禁止裸类型
- 优先使用接口类型声明集合

```java
// 推荐
List<String> names = new ArrayList<>();

// 不推荐
ArrayList names = new ArrayList();
```

## 注释规范
- 公共类和公共方法必须有 Javadoc
- 复杂逻辑必须有注释说明

## 其他
- 禁止在循环中拼接字符串，使用 `StringBuilder`
- 使用 `@Override` 注解重写的方法
