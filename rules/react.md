# React 代码规范

## 组件定义
- 优先使用函数组件和 Hooks
- 组件名使用 `PascalCase`
- 每个组件一个文件，文件名与组件名一致

```tsx
// 推荐
interface UserCardProps {
  name: string;
  age: number;
}

const UserCard: React.FC<UserCardProps> = ({ name, age }) => {
  return <div>{name}, {age}</div>;
};

export default UserCard;
```

## Hooks 规范
- 只在组件顶层调用 Hooks
- 自定义 Hook 以 `use` 开头

```tsx
// 推荐
const useUser = (id: number) => {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    fetchUser(id).then(setUser);
  }, [id]);

  return user;
};
```

## 状态管理
- 简单状态使用 `useState`
- 复杂状态使用 `useReducer`
- 跨组件共享使用 Context 或状态管理库

## 性能优化
- 使用 `React.memo` 避免不必要渲染
- 使用 `useMemo` 和 `useCallback` 缓存计算和回调
- 列表渲染使用稳定的 `key`

```tsx
// 推荐
const UserList: React.FC = React.memo(({ users }) => {
  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
});
```

## 事件处理
- 事件处理函数以 `handle` 开头
- 使用箭头函数或 `bind` 绑定 this

```tsx
// 推荐
const handleClick = (event: React.MouseEvent) => {
  console.log('clicked');
};

// 不推荐
<button onClick={(e) => { console.log(e); }}>Click</button>
```

## 样式规范
- 推荐 CSS Modules 或 Tailwind CSS
- 避免内联样式（动态样式除外）

## 目录结构
```
src/
├── components/       # 公共组件
├── hooks/            # 自定义 Hooks
├── pages/            # 页面组件
├── services/         # API 服务
├── stores/           # 状态管理
└── utils/            # 工具函数
```
