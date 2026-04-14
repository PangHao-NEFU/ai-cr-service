# Go 代码规范

## 代码风格
- 使用 `gofmt` 格式化代码
- 使用 `golint` 和 `go vet` 检查代码
- 每行不超过 120 字符

## 命名规范
- 包名：小写单词，不使用下划线（例：`httputil`）
- 变量和函数：`camelCase`，导出使用 `PascalCase`
- 接口：动词或形容词（例：`Reader`, `Writer`, `Stringer`）
- 常量：使用 `PascalCase` 或 `camelCase`

## 错误处理
- 错误必须处理，禁止忽略
- 使用 `errors.New()` 或 `fmt.Errorf()` 创建错误
- 错误信息不要大写开头，不要以标点结尾

```go
// 推荐
if err != nil {
    return fmt.Errorf("failed to open file: %w", err)
}

// 不推荐
if err != nil {
    // 忽略错误
}
```

## 资源管理
- 使用 `defer` 确保资源释放
- 文件、连接等必须在函数结束时关闭

```go
// 推荐
f, err := os.Open(path)
if err != nil {
    return err
}
defer f.Close()
```

## 并发编程
- 使用 `errgroup` 管理并发任务
- 使用 `context` 控制超时和取消
- 避免裸 `go` 关键字，确保 goroutine 可控

## 接口定义
- 接口在使用的包中定义，而非实现的包
- 保持接口最小化

## 注释规范
- 导出的函数、类型必须有注释
- 注释以函数/类型名开头

```go
// GetUserByID 根据用户ID获取用户信息。
func GetUserByID(id int64) (*User, error) {
    ...
}
```
