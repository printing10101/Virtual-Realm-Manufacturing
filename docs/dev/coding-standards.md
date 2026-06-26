# 编码规范

**版本**: 1.0.0  
**最后更新**: 2024-01-20  
**适用对象**: 全体开发人员

---

## 目录

1. [Python 编码规范](#python-编码规范)
2. [TypeScript/Vue 编码规范](#typescriptvue-编码规范)
3. [SQL 编码规范](#sql-编码规范)
4. [Git 提交规范](#git-提交规范)
5. [代码审查清单](#代码审查清单)

---

## Python 编码规范

### 代码风格

遵循 **PEP 8** 规范，使用 **Black** 进行代码格式化。

#### 格式化配置

```bash
# 使用 Black 格式化代码
black python/app/ --line-length 88

# 检查代码风格
flake8 python/app/ --max-line-length 88
```

#### 配置文件

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py310']

[tool.flake8]
max-line-length = 88
extend-ignore = E203, W503
```

### 命名规范

#### 类名

使用 **PascalCase**（大驼峰命名法）

```python
# ✅ 正确
class UserService:
    pass

class DataProcessor:
    pass

class LNNModel:
    pass

# ❌ 错误
class user_service:
    pass

class dataProcessor:
    pass
```

#### 函数和方法名

使用 **snake_case**（下划线命名法）

```python
# ✅ 正确
def get_user_by_id(user_id: int) -> User:
    pass

def calculate_total_price(items: list) -> float:
    pass

def _private_method(self):
    pass

# ❌ 错误
def getUserById(user_id: int):
    pass

def calculateTotalPrice(items: list):
    pass
```

#### 变量名

使用 **snake_case**（下划线命名法）

```python
# ✅ 正确
user_name = "John"
total_count = 100
is_active = True

# ❌ 错误
userName = "John"
totalCount = 100
isActive = True
```

#### 常量名

使用 **UPPER_SNAKE_CASE**（全大写加下划线）

```python
# ✅ 正确
MAX_RETRY_COUNT = 3
API_BASE_URL = "http://localhost:8765"
DEFAULT_TIMEOUT = 30

# ❌ 错误
maxRetryCount = 3
apiBaseUrl = "http://localhost:8765"
```

### 类型提示

**必须**使用类型提示，提高代码可读性和可维护性。

```python
# ✅ 正确
def process_task(
    task_id: int,
    user_id: int,
    priority: str = "normal"
) -> dict[str, Any]:
    """处理任务"""
    pass

class UserCreate(BaseModel):
    username: str
    email: str
    age: int | None = None

# ❌ 错误
def process_task(task_id, user_id, priority="normal"):
    pass
```

### 文档字符串

所有公共函数、类和方法**必须**包含文档字符串。

```python
def calculate_tool_wear(
    cutting_speed: float,
    feed_rate: float,
    cutting_time: float
) -> float:
    """
    计算刀具磨损量。
    
    Args:
        cutting_speed: 切削速度，单位 m/min
        feed_rate: 进给量，单位 mm/rev
        cutting_time: 切削时间，单位 min
        
    Returns:
        float: 预测的刀具磨损量，单位 mm
        
    Raises:
        ValueError: 当参数为负数时
        
    Example:
        >>> wear = calculate_tool_wear(200.0, 0.3, 30.0)
        >>> print(wear)
        0.15
    """
    if cutting_speed < 0 or feed_rate < 0 or cutting_time < 0:
        raise ValueError("参数不能为负数")
    
    # 计算逻辑
    wear = (cutting_speed * 0.001 + feed_rate * 0.1) * cutting_time / 1000
    return wear
```

### 导入规范

按照以下顺序组织导入：

1. 标准库导入
2. 第三方库导入
3. 本地/项目导入

```python
# ✅ 正确
# 标准库
import os
import sys
from datetime import datetime
from typing import Optional

# 第三方库
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

# 本地导入
from app.models.user import User
from app.services.user_service import UserService
from app.core.exceptions import BusinessException

# ❌ 错误
from app.models.user import User
import os
from fastapi import APIRouter
from datetime import datetime
```

### 异常处理

**不要**捕获所有异常，应该捕获特定异常。

```python
# ✅ 正确
try:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError(user_id)
except SQLAlchemyError as e:
    logger.error(f"数据库错误: {e}")
    raise DatabaseException("数据库查询失败") from e

# ❌ 错误
try:
    user = db.query(User).filter(User.id == user_id).first()
except Exception as e:
    # 捕获所有异常是不好的实践
    logger.error(f"错误: {e}")
    pass
```

### 注释规范

```python
# ✅ 好的注释 - 解释为什么
# 使用 LNN 模型而不是传统神经网络，因为需要融合领域规则
model = LNNModel(config)

# ✅ 好的注释 - 解释复杂的逻辑
# 先应用规则约束，再进行梯度更新
# 这样可以保证模型输出符合领域知识
loss = rule_loss + 0.1 * prediction_loss

# ❌ 避免的注释 - 显而易见的代码
# 增加 1
count += 1  # 不需要注释

# ❌ 避免的注释 - 注释掉的代码
# def old_function():
#     pass
# 删除代码应该直接删除，不要注释掉
```

---

## TypeScript/Vue 编码规范

### 代码风格

使用 **ESLint** + **Prettier** 进行代码格式化和检查。

#### 格式化配置

```bash
# 格式化代码
cd frontend
pnpm run format

# 检查代码
pnpm run lint
```

#### 配置文件

```javascript
// .eslintrc.cjs
module.exports = {
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-recommended',
    '@vue/typescript/recommended',
    'prettier'
  ],
  rules: {
    'vue/multi-word-component-names': 'off',
    '@typescript-eslint/no-explicit-any': 'warn'
  }
}
```

```json
// .prettierrc
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "none",
  "printWidth": 100
}
```

### 命名规范

#### 组件名

使用 **PascalCase**（大驼峰命名法）

```typescript
// ✅ 正确
const UserProfile = defineComponent({
  // ...
})

const TaskList = defineComponent({
  // ...
})

// ❌ 错误
const userProfile = defineComponent({
  // ...
})

const task_list = defineComponent({
  // ...
})
```

#### 变量和函数名

使用 **camelCase**（小驼峰命名法）

```typescript
// ✅ 正确
const userName = ref('John')
const taskCount = computed(() => tasks.value.length)

const getUserInfo = () => {
  // ...
}

const calculateTotal = (items: Item[]) => {
  // ...
}

// ❌ 错误
const user_name = ref('John')
const GetUserInfo = () => {
  // ...
}
```

#### 常量名

使用 **UPPER_SNAKE_CASE**（全大写加下划线）

```typescript
// ✅ 正确
const MAX_PAGE_SIZE = 100
const API_BASE_URL = '/api/v1'
const DEFAULT_TIMEOUT = 30000

// ❌ 错误
const maxPageSize = 100
const apiBaseUrl = '/api/v1'
```

#### 类型名

使用 **PascalCase**（大驼峰命名法）

```typescript
// ✅ 正确
interface UserInfo {
  id: number
  name: string
  email: string
}

type TaskStatus = 'pending' | 'running' | 'completed'

enum Priority {
  Low = 'low',
  Medium = 'medium',
  High = 'high'
}

// ❌ 错误
interface userInfo {
  id: number
}

type taskStatus = 'pending' | 'running'
```

### Vue 组件规范

#### 组件结构

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { UserInfo } from '@/types'
import { useUserStore } from '@/stores/user'

// 1. Props 定义
interface Props {
  userId: number
  showAvatar?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showAvatar: true
})

// 2. Emits 定义
const emit = defineEmits<{
  update: [user: UserInfo]
  delete: [userId: number]
}>()

// 3. Stores 和 Composables
const userStore = useUserStore()

// 4. 响应式数据
const userName = ref('')
const isLoading = ref(false)

// 5. 计算属性
const displayName = computed(() => {
  return userName.value.toUpperCase()
})

// 6. 方法
const handleUpdate = () => {
  emit('update', { id: props.userId, name: userName.value })
}

const handleSubmit = async () => {
  isLoading.value = true
  try {
    await userStore.updateUser(props.userId, { name: userName.value })
    emit('update', { id: props.userId, name: userName.value })
  } finally {
    isLoading.value = false
  }
}

// 7. 生命周期钩子
onMounted(() => {
  // 初始化逻辑
})
</script>

<template>
  <div class="user-profile">
    <div v-if="isLoading">加载中...</div>
    <div v-else>
      <h2>{{ displayName }}</h2>
      <button @click="handleUpdate">更新</button>
    </div>
  </div>
</template>

<style scoped>
.user-profile {
  padding: 20px;
}
</style>
```

#### 组件文件命名

```typescript
// ✅ 正确
// UserProfile.vue
// TaskList.vue
// LNNModelEditor.vue

// ❌ 错误
// userProfile.vue
// task-list.vue
// lnn_model_editor.vue
```

### TypeScript 类型规范

#### 避免使用 any

```typescript
// ✅ 正确
interface User {
  id: number
  name: string
  email: string
}

function getUser(id: number): Promise<User> {
  // ...
}

// ❌ 错误
function getUser(id: number): Promise<any> {
  // ...
}
```

#### 使用类型守卫

```typescript
// ✅ 正确
function isUser(obj: unknown): obj is User {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    'name' in obj &&
    'email' in obj
  )
}

// 使用
if (isUser(data)) {
  console.log(data.name) // TypeScript 知道 data 是 User 类型
}
```

---

## SQL 编码规范

### 命名规范

```sql
-- ✅ 正确
-- 表名：snake_case，复数形式
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引名：idx_表名_字段名
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- 外键名：fk_表名_引用表名
ALTER TABLE tasks
ADD CONSTRAINT fk_tasks_user_id
FOREIGN KEY (user_id) REFERENCES users(id);

-- ❌ 错误
CREATE TABLE User (
    ID INTEGER PRIMARY KEY,
    UserName TEXT
);

CREATE INDEX user_index ON User(UserName);
```

### 查询规范

```sql
-- ✅ 正确
-- 使用明确的列名，避免 SELECT *
SELECT 
    u.id,
    u.username,
    u.email,
    COUNT(t.id) AS task_count
FROM users u
LEFT JOIN tasks t ON u.id = t.user_id
WHERE u.created_at > datetime('now', '-30 days')
GROUP BY u.id, u.username, u.email
HAVING COUNT(t.id) > 5
ORDER BY task_count DESC
LIMIT 100;

-- ❌ 错误
SELECT * FROM users u LEFT JOIN tasks t ON u.id = t.user_id;
```

### 索引优化

```sql
-- ✅ 为常用查询字段创建索引
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_user_id ON tasks(user_id);

-- 复合索引（注意字段顺序）
CREATE INDEX idx_tasks_status_created 
ON tasks(status, created_at);

-- ❌ 避免过度索引
-- 每个索引都会增加写入开销
-- 只为真正需要的字段创建索引
```

---

## Git 提交规范

### 提交消息格式

使用 **Conventional Commits** 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型（type）

- **feat**: 新功能
- **fix**: 修复 bug
- **docs**: 文档更新
- **style**: 代码格式（不影响代码运行的变动）
- **refactor**: 重构（既不是新增功能，也不是修改 bug 的代码变动）
- **perf**: 性能优化
- **test**: 增加测试
- **chore**: 构建过程或辅助工具的变动

### 示例

```bash
# ✅ 好的提交消息
feat(api): 添加用户管理 API

- 实现用户 CRUD 接口
- 添加用户认证和授权
- 集成用户状态管理

Closes #123

fix(lnn): 修复刀具磨损预测精度问题

- 调整模型参数
- 优化特征工程
- 更新训练数据

Performance: 预测精度提升 15%

docs(readme): 更新安装指南

- 添加 Windows 安装步骤
- 更新依赖版本要求

# ❌ 不好的提交消息
update code
fix bug
修改了一些东西
```

### 分支命名

```bash
# 功能分支
feature/user-authentication
feature/lnn-model-optimization

# 修复分支
fix/database-connection-issue
fix/api-timeout-error

# 发布分支
release/v2.0.0
release/v2.1.0

# 热修复分支
hotfix/critical-security-issue
```

---

## 代码审查清单

### Python 代码审查

- [ ] 代码符合 PEP 8 规范
- [ ] 使用 Black 格式化
- [ ] 所有公共函数都有类型提示
- [ ] 所有公共函数都有文档字符串
- [ ] 没有硬编码的配置值
- [ ] 异常处理合理，没有捕获所有异常
- [ ] 导入按顺序组织
- [ ] 命名符合规范
- [ ] 没有注释掉的代码
- [ ] 单元测试覆盖关键逻辑

### TypeScript/Vue 代码审查

- [ ] 代码通过 ESLint 检查
- [ ] 使用 Prettier 格式化
- [ ] 组件命名符合规范
- [ ] Props 和 Emits 有类型定义
- [ ] 避免使用 any 类型
- [ ] 响应式数据使用正确
- [ ] 组件结构清晰
- [ ] 样式使用 scoped
- [ ] 没有硬编码的配置值
- [ ] 单元测试覆盖关键逻辑

### SQL 代码审查

- [ ] 表名和字段名符合命名规范
- [ ] 避免使用 SELECT *
- [ ] 查询有适当的索引
- [ ] 没有 SQL 注入风险
- [ ] 外键约束正确
- [ ] 查询性能合理

### 通用审查

- [ ] 代码逻辑正确
- [ ] 没有安全漏洞
- [ ] 性能无明显问题
- [ ] 文档已更新
- [ ] 提交消息符合规范
- [ ] 没有引入不必要的依赖

---

## 相关资源

### 内部资源

- [开发者指南 README](./README.md)
- [开发环境搭建](./environment-setup.md)
- [API 开发指南](./api-development.md)
- [测试指南](./testing-guide.md)

### 外部资源

- [PEP 8 规范](https://peps.python.org/pep-0008/)
- [Black 文档](https://black.readthedocs.io/)
- [Vue 3 风格指南](https://vuejs.org/style-guide/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

**最后更新**: 2024-01-20  
**维护者**: 开发团队
