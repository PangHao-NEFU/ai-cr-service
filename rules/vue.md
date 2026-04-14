# Vue 代码规范

## 组件定义
- 使用 SFC（单文件组件）：`.vue` 文件
- 组件名使用 `PascalCase`
- Props 必须定义类型

```vue
<!-- 推荐 -->
<script setup lang="ts">
interface Props {
  title: string;
  count?: number;
}

const props = withDefaults(defineProps<Props>(), {
  count: 0,
});
</script>
```

## 命名规范
- 组件文件：`PascalCase.vue`（例：`UserCard.vue`）
- 组件名：`PascalCase`
- Props：`camelCase`
- 自定义事件：`kebab-case`

## 组合式 API
- 优先使用 `<script setup>` 语法
- 使用 Composition API 组织代码

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';

const count = ref(0);
const doubled = computed(() => count.value * 2);

onMounted(() => {
  console.log('mounted');
});
</script>
```

## 模板规范
- 使用 `v-model` 替代 `:value` + `@input`
- 使用 `v-if` 条件渲染，`v-show` 频繁切换
- 列表使用 `:key` 绑定唯一标识

```vue
<!-- 推荐 -->
<ul>
  <li v-for="item in items" :key="item.id">
    {{ item.name }}
  </li>
</ul>
```

## 样式规范
- 使用 `<style scoped>` 限定作用域
- 推荐 CSS Modules 或 Tailwind CSS

## 状态管理
- 简单状态使用 `ref` / `reactive`
- 跨组件使用 Pinia

## 目录结构
```
src/
├── components/       # 公共组件
├── composables/      # 组合式函数
├── views/            # 页面组件
├── stores/           # Pinia 状态
├── api/              # API 接口
└── utils/            # 工具函数
```

## TypeScript 支持
- 使用 `defineProps` 和 `defineEmits` 的泛型语法
- API 响应定义类型接口
