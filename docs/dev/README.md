# 灵境制造系统开发者指南

**版本**: 1.0.0  
**最后更新**: 2024-01-20  
**维护团队**: 开发团队

---

## 目录

1. [快速开始](#快速开始)
2. [开发环境搭建](#开发环境搭建)
3. [项目架构](#项目架构)
4. [编码规范](#编码规范)
5. [API 开发指南](#api-开发指南)
6. [LNN 引擎开发](#lnn-引擎开发)
7. [测试指南](#测试指南)
8. [Git 工作流](#git-工作流)
9. [常见问题](#常见问题)

---

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- pnpm 8+
- Git

### 5 分钟快速启动

```bash
# 1. 克隆项目
git clone https://github.com/your-org/lingjing-manufacturing.git
cd lingjing-manufacturing

# 2. 安装后端依赖
cd python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 初始化数据库
alembic upgrade head

# 4. 启动后端服务
python start_server.py

# 5. 安装前端依赖（新终端）
cd frontend
pnpm install

# 6. 启动前端开发服务器
pnpm dev
```

访问：
- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

---

## 开发环境搭建

### 系统要求

**操作系统**：
- Windows 10/11
- macOS 12+
- Linux (Ubuntu 20.04+, CentOS 8+)

**硬件要求**：
- CPU：4 核+
- 内存：8 GB+（推荐 16 GB）
- 存储：20 GB 可用空间

### 工具安装

#### 1. Python 环境

```bash
# 安装 Python 3.10+
# macOS
brew install python@3.10

# Ubuntu
sudo apt install python3.10 python3.10-venv

# Windows
# 下载 installer: https://www.python.org/downloads/
```

#### 2. Node.js 环境

```bash
# 使用 nvm 管理 Node.js 版本
# macOS/Linux
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18

# Windows
# 下载 nvm-windows: https://github.com/coreybutler/nvm-windows
```

#### 3. 包管理器

```bash
# 安装 pnpm
npm install -g pnpm

# 验证安装
pnpm --version
```

#### 4. 数据库工具

```bash
# SQLite 命令行工具
# macOS
brew install sqlite

# Ubuntu
sudo apt install sqlite3

# Windows
# 下载: https://www.sqlite.org/download.html
```

#### 5. IDE 推荐

**VS Code**（推荐）：
```bash
# 安装扩展
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension vue.volar
```

**PyCharm**：
- Professional 版（推荐）或 Community 版
- 安装 Vue.js 插件

---

## 项目架构

### 目录结构

```
lingjing-manufacturing/
├── python/                 # 后端代码
│   ├── app/               # 主应用
│   │   ├── api/          # API 路由
│   │   ├── ai/           # AI 模块（LNN）
│   │   ├── core/         # 核心功能
│   │   ├── database/     # 数据库
│   │   ├── models/       # 数据模型
│   │   └── services/     # 业务服务
│   ├── tests/            # 测试代码
│   ├── alembic/          # 数据库迁移
│   └── scripts/          # 脚本工具
│
├── frontend/             # 前端代码
│   ├── src/
│   │   ├── api/         # API 调用
│   │   ├── components/  # 组件
│   │   ├── views/       # 页面
│   │   ├── stores/      # 状态管理
│   │   └── utils/       # 工具函数
│   └── tests/           # 测试代码
│
├── config/               # 配置文件
├── docs/                 # 文档
└── deploy/              # 部署配置
```

### 后端架构

#### 分层架构

```
API Layer (FastAPI)
    ↓
Service Layer (业务逻辑)
    ↓
Repository Layer (数据访问)
    ↓
Database Layer (SQLite)
```

#### 核心模块

1. **API 层** (`app/api/`)
   - 路由定义
   - 请求验证
   - 响应格式化

2. **服务层** (`app/services/`)
   - 业务逻辑
   - 事务管理
   - 外部服务集成

3. **数据层** (`app/database/`)
   - 数据模型
   - 数据库连接
   - 查询构建

4. **AI 模块** (`app/ai/`)
   - LNN 引擎
   - 模型管理
   - 推理服务

### 前端架构

#### 组件化架构

```
Views (页面)
    ↓
Components (组件)
    ↓
Composables (组合式函数)
    ↓
Stores (状态管理)
    ↓
API (后端调用)
```

#### 核心目录

1. **Views** (`src/views/`)
   - 页面级组件
   - 路由对应

2. **Components** (`src/components/`)
   - 可复用组件
   - UI 组件库

3. **Composables** (`src/composables/`)
   - 组合式函数
   - 业务逻辑封装

4. **Stores** (`src/stores/`)
   - Pinia 状态管理
   - 全局状态

---

## 编码规范

### Python 编码规范

#### 代码风格

遵循 **PEP 8** 规范，使用 **Black** 格式化：

```bash
# 格式化代码
black python/app/

# 检查代码
flake8 python/app/
```

#### 命名规范

```python
# 类名：PascalCase
class UserService:
    pass

# 函数和变量：snake_case
def get_user_by_id(user_id: int) -> User:
    user_name = "John"
    return user

# 常量：UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
API_BASE_URL = "http://localhost:8000"

# 私有成员：前缀下划线
class MyClass:
    def _private_method(self):
        pass
```

#### 类型提示

```python
# 必须使用类型提示
def calculate_total(
    items: list[Item],
    discount: float = 0.0
) -> float:
    total = sum(item.price for item in items)
    return total * (1 - discount)

# 使用 Pydantic 模型
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    age: int | None = None
```

#### 文档字符串

```python
def process_task(task_id: int) -> TaskResult:
    """
    处理指定的任务。
    
    Args:
        task_id: 任务的唯一标识符
        
    Returns:
        TaskResult: 任务处理结果
        
    Raises:
        TaskNotFoundError: 当任务不存在时
        TaskProcessingError: 当任务处理失败时
        
    Example:
        >>> result = process_task(123)
        >>> print(result.status)
        'completed'
    """
    pass
```

### TypeScript/Vue 编码规范

#### 代码风格

使用 **ESLint** + **Prettier**：

```bash
# 格式化代码
cd frontend
pnpm run format

# 检查代码
pnpm run lint
```

#### 命名规范

```typescript
// 组件名：PascalCase
const UserProfile = defineComponent({
  // ...
})

// 变量和函数：camelCase
const userName = ref('John')
const getUserInfo = () => {
  // ...
}

// 常量：UPPER_SNAKE_CASE
const MAX_PAGE_SIZE = 100
const API_BASE_URL = '/api/v1'

// 类型：PascalCase
interface UserInfo {
  id: number
  name: string
}

type TaskStatus = 'pending' | 'running' | 'completed'
```

#### 组件规范

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { UserInfo } from '@/types'

// Props 定义
interface Props {
  userId: number
  showAvatar?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showAvatar: true
})

// Emits 定义
const emit = defineEmits<{
  update: [user: UserInfo]
  delete: [userId: number]
}>()

// 响应式数据
const userName = ref('')

// 计算属性
const displayName = computed(() => {
  return userName.value.toUpperCase()
})

// 方法
const handleUpdate = () => {
  emit('update', { id: props.userId, name: userName.value })
}
</script>

<template>
  <div class="user-profile">
    <!-- 模板内容 -->
  </div>
</template>

<style scoped>
.user-profile {
  /* 样式 */
}
</style>
```

### SQL 编码规范

```sql
-- 表名和字段名：snake_case
CREATE TABLE user_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 索引命名：idx_表名_字段名
CREATE INDEX idx_user_tasks_user_id ON user_tasks(user_id);
CREATE INDEX idx_user_tasks_created ON user_tasks(created_at);

-- 查询规范
SELECT 
    ut.id,
    ut.task_name,
    u.username
FROM user_tasks ut
INNER JOIN users u ON ut.user_id = u.id
WHERE ut.created_at > datetime('now', '-7 days')
ORDER BY ut.created_at DESC
LIMIT 100;
```

---

## API 开发指南

### 创建新 API

#### 1. 定义路由

```python
# app/api/v1/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.user import User, UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["用户管理"])

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    创建新用户
    """
    # 检查用户是否已存在
    existing_user = db.query(User).filter(
        User.username == user_data.username
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="用户名已存在"
        )
    
    # 创建用户
    new_user = User(**user_data.dict())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    获取用户信息
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="用户不存在"
        )
    
    return user
```

#### 2. 注册路由

```python
# app/api/v1/__init__.py
from fastapi import APIRouter
from .users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(users_router)
```

#### 3. 添加测试

```python
# tests/api/test_users.py
import pytest
from fastapi.testclient import TestClient

def test_create_user(client: TestClient):
    """测试创建用户"""
    response = client.post(
        "/api/v1/users/",
        json={
            "username": "testuser",
            "email": "test@example.com"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data

def test_get_user(client: TestClient, test_user):
    """测试获取用户"""
    response = client.get(f"/api/v1/users/{test_user.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
```

### API 最佳实践

#### 1. 使用依赖注入

```python
# 定义依赖
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    
    return user

# 使用依赖
@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    return current_user
```

#### 2. 统一错误处理

```python
# app/core/exceptions.py
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

class BusinessException(HTTPException):
    """业务异常基类"""
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict | None = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message,
                "details": details or {}
            }
        )

class UserNotFoundError(BusinessException):
    def __init__(self, user_id: int):
        super().__init__(
            status_code=404,
            error_code="USER_NOT_FOUND",
            message=f"用户 {user_id} 不存在"
        )

# 全局异常处理器
@app.exception_handler(BusinessException)
async def business_exception_handler(
    request: Request,
    exc: BusinessException
):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
    )
```

#### 3. 分页实现

```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取用户列表（分页）"""
    offset = (page - 1) * page_size
    
    users = db.query(User).offset(offset).limit(page_size).all()
    total = db.query(User).count()
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
```

---

## LNN 引擎开发

### LNN 基础

#### 什么是 LNN

LNN（Logical Neural Network）是一种融合逻辑规则和神经网络的新型 AI 架构，具有以下特点：

- **可解释性**：网络结构对应逻辑规则
- **知识融合**：支持嵌入领域专家规则
- **不确定性量化**：提供预测置信度

#### LNN 模型类型

1. **CFC（Continuous Fluid Dynamics）**
   - 适用于连续过程建模
   - 适合工艺参数优化

2. **LTC（Liquid Time Constant）**
   - 适用于时序数据
   - 适合刀具磨损预测

### 创建 LNN 模型

#### 1. 定义模型结构

```python
# app/ai/lnn/models/custom_lnn.py
from app.ai.lnn.models.base_lnn import BaseLNN
import torch.nn as nn

class CustomLNN(BaseLNN):
    """自定义 LNN 模型"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        
        # 定义网络层
        self.feature_extractor = nn.Sequential(
            nn.Linear(config['input_dim'], 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU()
        )
        
        self.logic_layer = nn.Linear(32, config['output_dim'])
        
    def forward(self, x):
        features = self.feature_extractor(x)
        output = self.logic_layer(features)
        return output
```

#### 2. 添加规则约束

```python
# app/ai/lnn/rules/tool_wear_rules.py
from app.ai.lnn.rule_converter import RuleConverter

class ToolWearRules:
    """刀具磨损规则"""
    
    @staticmethod
    def get_rules():
        """
        规则 1: 如果切削速度 > 200 m/min，则磨损加速
        规则 2: 如果进给量 > 0.5 mm/rev，则磨损增加
        规则 3: 如果切削时间 > 60 min，则磨损显著
        """
        rules = [
            {
                "condition": "cutting_speed > 200",
                "effect": "wear_rate * 1.5",
                "confidence": 0.8
            },
            {
                "condition": "feed_rate > 0.5",
                "effect": "wear_rate * 1.3",
                "confidence": 0.7
            },
            {
                "condition": "cutting_time > 60",
                "effect": "wear_rate * 1.2",
                "confidence": 0.9
            }
        ]
        
        return RuleConverter.convert(rules)
```

#### 3. 训练模型

```python
# scripts/train_lnn_model.py
from app.ai.lnn.training.trainer import LNNTrainer
from app.ai.lnn.models.custom_lnn import CustomLNN

def train_model():
    # 配置
    config = {
        'input_dim': 10,
        'output_dim': 1,
        'learning_rate': 0.001,
        'epochs': 100,
        'batch_size': 32
    }
    
    # 创建模型
    model = CustomLNN(config)
    
    # 创建训练器
    trainer = LNNTrainer(
        model=model,
        config=config,
        rules=ToolWearRules.get_rules()
    )
    
    # 加载数据
    train_data, val_data = load_training_data()
    
    # 训练
    trainer.train(
        train_data=train_data,
        val_data=val_data
    )
    
    # 保存模型
    trainer.save_model('models/tool_wear_lnn_v1.pkl')

if __name__ == '__main__':
    train_model()
```

#### 4. 部署模型

```python
# app/ai/lnn/router/predict.py
from fastapi import APIRouter, Depends
from app.ai.lnn.engine import LNNEngine

router = APIRouter()

@router.post("/predict/tool-wear")
async def predict_tool_wear(
    request: ToolWearRequest,
    engine: LNNEngine = Depends(get_lnn_engine)
):
    """预测刀具磨损"""
    # 推理
    result = engine.predict(
        model_name='tool_wear_lnn_v1',
        features=request.features
    )
    
    return {
        "predicted_wear": result.value,
        "confidence": result.confidence,
        "uncertainty": result.uncertainty
    }
```

### LNN 调试技巧

```python
# 启用调试模式
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看规则激活情况
engine = LNNEngine(debug=True)
result = engine.predict(model_name, features)
print(result.rule_activations)

# 可视化网络结构
engine.visualize_graph(model_name, save_path='graph.png')
```

---

## 测试指南

### 测试策略

#### 测试金字塔

```
        /  E2E  \        <- 少量端到端测试
       /--------\
      / 集成测试  \      <- 适量集成测试
     /------------\
    /   单元测试    \    <- 大量单元测试
   /----------------\
```

### 单元测试

#### Python 单元测试

```python
# tests/unit/test_user_service.py
import pytest
from unittest.mock import Mock
from app.services.user_service import UserService

def test_create_user_success():
    """测试创建用户成功"""
    # 准备
    mock_db = Mock()
    service = UserService(mock_db)
    
    user_data = {
        "username": "testuser",
        "email": "test@example.com"
    }
    
    # 执行
    result = service.create_user(user_data)
    
    # 验证
    assert result.username == "testuser"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

def test_create_user_duplicate():
    """测试创建重复用户"""
    # 准备
    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = Mock()
    
    service = UserService(mock_db)
    user_data = {
        "username": "existinguser",
        "email": "test@example.com"
    }
    
    # 执行和验证
    with pytest.raises(BusinessException) as exc_info:
        service.create_user(user_data)
    
    assert exc_info.value.error_code == "USER_ALREADY_EXISTS"
```

#### 前端单元测试

```typescript
// tests/unit/UserProfile.spec.ts
import { mount } from '@vue/test-utils'
import UserProfile from '@/components/UserProfile.vue'
import { describe, it, expect } from 'vitest'

describe('UserProfile', () => {
  it('renders user name correctly', () => {
    const wrapper = mount(UserProfile, {
      props: {
        userId: 1,
        userName: 'John Doe'
      }
    })
    
    expect(wrapper.text()).toContain('John Doe')
  })
  
  it('emits update event', async () => {
    const wrapper = mount(UserProfile, {
      props: { userId: 1 }
    })
    
    await wrapper.find('button').trigger('click')
    
    expect(wrapper.emitted('update')).toBeTruthy()
  })
})
```

### 集成测试

```python
# tests/integration/test_user_api.py
from fastapi.testclient import TestClient

def test_user_workflow(client: TestClient):
    """测试用户完整工作流"""
    # 1. 创建用户
    response = client.post(
        "/api/v1/users/",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "securepassword"
        }
    )
    assert response.status_code == 201
    user_id = response.json()["id"]
    
    # 2. 获取用户
    response = client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
    
    # 3. 更新用户
    response = client.put(
        f"/api/v1/users/{user_id}",
        json={"email": "newemail@example.com"}
    )
    assert response.status_code == 200
    
    # 4. 删除用户
    response = client.delete(f"/api/v1/users/{user_id}")
    assert response.status_code == 204
```

### 运行测试

```bash
# Python 测试
cd python
pytest                              # 运行所有测试
pytest tests/unit/                  # 运行单元测试
pytest tests/integration/           # 运行集成测试
pytest -v                           # 详细输出
pytest --cov=app                    # 覆盖率报告

# 前端测试
cd frontend
pnpm test                           # 运行所有测试
pnpm test:unit                      # 运行单元测试
pnpm test:e2e                       # 运行端到端测试
pnpm test:coverage                  # 覆盖率报告
```

---

## Git 工作流

### 分支策略

```
main (生产分支)
  ↑
  | merge
  |
develop (开发分支)
  ↑
  | merge
  |
feature/user-auth (功能分支)
```

### 提交规范

使用 **Conventional Commits**：

```bash
# 类型
feat:     新功能
fix:      修复 bug
docs:     文档更新
style:    代码格式（不影响代码运行）
refactor: 重构
test:     测试相关
chore:    构建过程或辅助工具变动

# 示例
feat(api): 添加用户管理 API
fix(lnn): 修复刀具磨损预测精度问题
docs(readme): 更新安装指南
refactor(database): 重构数据库连接池
```

### Pull Request 流程

1. **创建功能分支**
   ```bash
   git checkout -b feature/user-auth
   ```

2. **开发和提交**
   ```bash
   git add .
   git commit -m "feat(auth): 实现用户认证"
   ```

3. **推送到远程**
   ```bash
   git push origin feature/user-auth
   ```

4. **创建 Pull Request**
   - 标题：`feat(auth): 实现用户认证`
   - 描述：说明实现的功能和测试情况
   - 指定 Reviewer

5. **代码审查**
   - 至少 1 个 Reviewer 批准
   - 所有 CI 检查通过
   - 无未解决的评论

6. **合并**
   - 使用 Squash and Merge
   - 删除功能分支

### Code Review 要点

- [ ] 代码符合编码规范
- [ ] 有充分的单元测试
- [ ] 无安全漏洞
- [ ] 性能无明显问题
- [ ] 文档已更新
- [ ] 无硬编码配置

---

## 常见问题

### Q1: 数据库锁定问题

**问题**：`Error: database is locked`

**解决**：
```python
# 增加超时时间
from sqlalchemy import create_engine
engine = create_engine(
    "sqlite:///./data/lingjing.db",
    connect_args={
        "timeout": 30,
        "check_same_thread": False
    }
)

# 启用 WAL 模式
with engine.connect() as conn:
    conn.execute("PRAGMA journal_mode=WAL")
```

### Q2: LNN 模型加载缓慢

**问题**：首次加载模型需要很长时间

**解决**：
```python
# 启用模型缓存
from app.ai.lnn.engine import LNNEngine

engine = LNNEngine(
    cache_enabled=True,
    cache_size=100  # 缓存 100 个模型
)

# 预热常用模型
engine.warmup(['tool_wear_v1', 'process_opt_v1'])
```

### Q3: 前端热更新失效

**问题**：修改代码后页面不自动刷新

**解决**：
```bash
# 清除缓存
cd frontend
rm -rf node_modules/.vite
pnpm dev

# 或检查端口占用
lsof -ti:3000 | xargs kill -9
```

### Q4: 内存泄漏

**问题**：服务运行一段时间后内存持续增长

**解决**：
```python
# 检查数据库连接泄漏
from app.database.connection import get_db

# 确保使用依赖注入
@router.get("/users")
async def get_users(db: Session = Depends(get_db)):
    # db 会自动关闭
    return db.query(User).all()

# 检查大对象缓存
import gc
gc.collect()  # 手动触发垃圾回收
```

### Q5: API 文档无法访问

**问题**：访问 `/docs` 返回 404

**解决**：
```python
# 检查 FastAPI 配置
from fastapi import FastAPI

app = FastAPI(
    docs_url="/docs",      # 确保启用
    redoc_url="/redoc",    # ReDoc 文档
    openapi_url="/openapi.json"
)
```

---

## 相关资源

### 内部资源

- [API 文档](http://localhost:8000/docs)
- [架构概述](./架构概述.md)
- [测试指南](./测试指南.md)
- [贡献指南](./贡献指南.md)

### 外部资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Vue 3 官方文档](https://vuejs.org/)
- [PyTorch 官方文档](https://pytorch.org/docs/)
- [SQLite 官方文档](https://www.sqlite.org/docs.html)

---

## 联系支持

- **技术问题**：dev-support@your-company.com
- **代码审查**：通过 GitHub Pull Request
- **紧急问题**：+86-xxx-xxxx-xxxx

---

**最后更新**: 2024-01-20  
**维护者**: 开发团队
