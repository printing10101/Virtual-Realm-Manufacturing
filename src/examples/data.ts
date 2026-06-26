/**
 * 示例工程库数据
 * 包含10+个真实业务场景的完整示例工程
 */

import type { ExampleProject } from './types'

export const exampleProjects: ExampleProject[] = [
  {
    id: 'basic-cube-modeling',
    name: '基础立方体建模',
    description: '学习如何使用基础几何体创建立方体模型',
    details: `# 基础立方体建模

## 学习目标
- 掌握基础几何体的创建方法
- 理解坐标系统和尺寸参数
- 学习材质和颜色的基本设置

## 应用场景
- 产品包装设计
- 建筑模型原型
- 教学演示

## 关键步骤
1. 创建立方体几何体
2. 设置尺寸参数（长宽高）
3. 应用基础材质
4. 调整位置和旋转

## 代码说明
本示例展示了如何使用 Three.js 创建基础立方体，并设置其位置、旋转和材质属性。`,
    category: 'basic',
    difficulty: 'beginner',
    tags: ['基础', '几何体', '入门'],
    code: `// 创建立方体几何体
const geometry = new THREE.BoxGeometry(10, 10, 10);

// 创建材质
const material = new THREE.MeshPhongMaterial({
  color: 0x00ff00,
  shininess: 80
});

// 创建网格对象
const cube = new THREE.Mesh(geometry, material);

// 设置位置
cube.position.set(0, 0, 0);

// 设置旋转（弧度）
cube.rotation.x = Math.PI / 4;
cube.rotation.y = Math.PI / 4;

// 添加到场景
scene.add(cube);`,
    language: 'typescript',
    useCases: [
      '产品包装设计原型',
      '建筑模型基础组件',
      '3D打印模型准备',
      '教学演示案例'
    ],
    createdAt: '2024-01-15',
    updatedAt: '2024-03-20',
    downloadCount: 1520
  },
  {
    id: 'toolpath-simple-milling',
    name: '简单铣削工具路径',
    description: '创建2D轮廓铣削工具路径，适合平板类零件加工',
    details: `# 简单铣削工具路径

## 学习目标
- 理解工具路径的基本概念
- 掌握2D轮廓铣削的参数设置
- 学习切削参数优化

## 应用场景
- 平板类零件加工
- 模具型腔粗加工
- 钣金件下料

## 关键参数
- 切削速度：根据材料选择
- 进给速率：影响加工效率
- 切深：单次切削深度
- 步距：相邻路径重叠量

## 工艺建议
1. 先进行粗加工，留0.5mm余量
2. 精加工时降低进给速率
3. 注意刀具磨损监控`,
    category: 'toolpath',
    difficulty: 'beginner',
    tags: ['工具路径', '铣削', 'CNC'],
    code: `// 定义工具路径参数
const toolpathParams = {
  type: 'contour_2d',
  toolDiameter: 10,        // 刀具直径 mm
  cuttingSpeed: 200,       // 切削速度 m/min
  feedRate: 500,           // 进给速率 mm/min
  depthPerCut: 2,          // 单次切深 mm
  stepOver: 5,             // 步距 mm
  clearanceHeight: 10      // 安全高度 mm
};

// 生成工具路径
const toolpath = generateContourToolpath(
  contourPoints,
  toolpathParams
);

// 验证路径
const validation = validateToolpath(toolpath);
if (validation.isValid) {
  exportGCode(toolpath);
}`,
    language: 'typescript',
    useCases: [
      '平板零件批量加工',
      '模具型腔粗加工',
      '钣金件下料路径',
      '教学演示CNC编程'
    ],
    createdAt: '2024-02-01',
    updatedAt: '2024-03-15',
    downloadCount: 2340
  },
  {
    id: 'toolpath-turning-operations',
    name: '车削加工路径',
    description: '创建数控车削加工路径，适用于轴类零件',
    details: `# 车削加工路径

## 学习目标
- 掌握数控车削编程方法
- 理解车削工艺参数
- 学习刀具选择与切削优化

## 应用场景
- 轴类零件加工
- 盘套类零件
- 螺纹加工
- 成型面车削

## 车削类型
- 外圆车削
- 内孔车削
- 端面车削
- 切槽切断
- 螺纹车削

## 工艺要点
1. 合理选择主轴转速
2. 优化进给速率
3. 控制切削深度
4. 考虑刀具寿命`,
    category: 'toolpath',
    difficulty: 'beginner',
    tags: ['车削', 'CNC', '数控车', '工具路径'],
    code: `// 定义车削参数
const turningParams = {
  operation: 'outer_diameter',
  material: '45Steel',
  diameter: 50,           // 工件直径 mm
  length: 100,            // 加工长度 mm
  spindleSpeed: 800,      // 主轴转速 rpm
  feedRate: 0.2,          // 进给量 mm/rev
  depthOfCut: 2,          // 切削深度 mm
  finishAllowance: 0.5    // 精加工余量 mm
};

// 定义刀具
const tool = {
  type: 'external_turning',
  insert: 'CNMG120408',
  grade: 'P25',
  rakeAngle: 15
};

// 生成车削路径
const turningPath = generateTurningToolpath({
  profile: contourProfile,
  params: turningParams,
  tool: tool,
  strategy: 'rough_then_finish'
});

// 验证切削参数
const validation = validateTurningParams(turningPath);
if (validation.isValid) {
  // 计算加工时间
  const machiningTime = calculateTurningTime(turningPath);
  
  // 导出G代码
  exportGCode(turningPath, 'shaft_part.nc');
}`,
    language: 'typescript',
    useCases: [
      '轴类零件批量加工',
      '阶梯轴车削',
      '螺纹轴加工',
      '数控车编程教学'
    ],
    createdAt: '2024-02-25',
    updatedAt: '2024-03-28',
    downloadCount: 1650
  },
  {
    id: 'simulation-thermal-analysis',
    name: '热力学仿真分析',
    description: '对加工过程进行温度场仿真，预测热变形',
    details: `# 热力学仿真分析

## 学习目标
- 理解切削热的产生机理
- 掌握温度场仿真设置
- 分析热变形对精度的影响

## 应用场景
- 高速加工优化
- 难加工材料工艺优化
- 精密加工误差控制

## 仿真参数
- 材料热导率
- 比热容
- 切削热分配系数
- 环境温度
- 冷却条件

## 结果分析
通过温度场分布云图，识别高温区域，优化切削参数以降低热变形。`,
    category: 'simulation',
    difficulty: 'advanced',
    tags: ['仿真', '热力学', '温度场'],
    code: `// 定义材料热学参数
const materialProps = {
  thermalConductivity: 45,  // W/(m·K)
  specificHeat: 500,        // J/(kg·K)
  density: 7800,            // kg/m³
  expansionCoeff: 1.2e-5    // 1/K
};

// 定义切削条件
const cuttingConditions = {
  cuttingSpeed: 150,        // m/min
  feedRate: 0.2,            // mm/rev
  depthOfCut: 3,            // mm
  coolantTemp: 20,          // °C
  coolantFlow: 10           // L/min
};

// 创建热力学仿真
const thermalSim = new ThermalSimulation({
  geometry: workpiece,
  material: materialProps,
  conditions: cuttingConditions,
  meshSize: 0.5             // mm
});

// 运行仿真
const result = await thermalSim.run();

// 获取最高温度
const maxTemp = result.getMaxTemperature();

// 获取热变形
const deformation = result.getThermalDeformation();`,
    language: 'typescript',
    useCases: [
      '高速加工工艺优化',
      '难加工材料（钛合金、高温合金）加工',
      '精密零件误差预测',
      '冷却系统效果评估'
    ],
    createdAt: '2024-01-20',
    updatedAt: '2024-03-25',
    downloadCount: 890
  },
  {
    id: 'ai-feature-recognition',
    name: 'AI特征识别',
    description: '使用AI自动识别模型中的加工特征（孔、槽、台阶等）',
    details: `# AI特征识别

## 学习目标
- 理解AI特征识别原理
- 掌握特征类型分类
- 学习特征参数提取

## 应用场景
- 自动化工艺规划
- 加工时间估算
- 成本评估

## 支持的特征类型
- 通孔/盲孔
- 台阶面
- 槽（直槽、T型槽）
- 倒角/圆角
- 螺纹孔

## AI模型说明
使用深度学习模型（PointNet++）对3D模型进行特征识别，准确率可达95%以上。`,
    category: 'ai',
    difficulty: 'intermediate',
    tags: ['AI', '特征识别', '自动化'],
    code: `// 加载3D模型
const model = await loadModel('part.step');

// 初始化AI特征识别器
const featureRecognizer = new AIRFeatureRecognizer({
  modelPath: 'models/feature_recognition_v2.pth',
  confidenceThreshold: 0.85
});

// 执行特征识别
const features = await featureRecognizer.recognize(model);

// 输出识别结果
features.forEach(feature => {
  // 特征类型、置信度、参数和加工建议
});

// 统计特征数量
const summary = featureRecognizer.getSummary(features);`,
    language: 'typescript',
    useCases: [
      '自动化工艺路线生成',
      '加工时间快速估算',
      '零件成本评估',
      '可制造性分析'
    ],
    createdAt: '2024-02-10',
    updatedAt: '2024-03-28',
    downloadCount: 1780
  },
  {
    id: 'modeling-assembly-design',
    name: '装配体设计',
    description: '创建多零件装配体，定义配合关系和运动约束',
    details: `# 装配体设计

## 学习目标
- 掌握装配体创建方法
- 理解配合关系类型
- 学习干涉检查

## 应用场景
- 产品设计验证
- 装配工艺规划
- 运动仿真

## 配合关系类型
- 面贴合
- 轴孔配合
- 齿轮啮合
- 凸轮接触

## 设计流程
1. 导入或创建零件
2. 定义基准面和坐标系
3. 添加配合约束
4. 检查干涉和间隙
5. 生成爆炸视图`,
    category: 'modeling',
    difficulty: 'intermediate',
    tags: ['装配体', '配合', '设计'],
    code: `// 创建装配体
const assembly = new Assembly('齿轮箱装配体');

// 导入零件
const housing = await loadPart('housing.step');
const gear1 = await loadPart('gear1.step');
const gear2 = await loadPart('gear2.step');
const shaft = await loadPart('shaft.step');

// 添加零件到装配体
assembly.addComponent(housing, { fixed: true });
assembly.addComponent(gear1, { name: '主动齿轮' });
assembly.addComponent(gear2, { name: '从动齿轮' });
assembly.addComponent(shaft, { name: '输出轴' });

// 定义配合关系
assembly.addConstraint({
  type: 'coaxial',
  parts: ['shaft', 'housing.bore1']
});

assembly.addConstraint({
  type: 'gear_mesh',
  parts: ['主动齿轮', '从动齿轮'],
  ratio: 2.5,
  centerDistance: 75
});

// 干涉检查
const interference = assembly.checkInterference();
if (interference.hasInterference) {
  // 处理干涉情况
}

// 生成爆炸视图
const explodedView = assembly.createExplodedView({
  direction: 'z',
  distance: 100
});`,
    language: 'typescript',
    useCases: [
      '机械产品设计验证',
      '装配工艺规划',
      '运动仿真前处理',
      '装配指导书生成'
    ],
    createdAt: '2024-02-05',
    updatedAt: '2024-03-22',
    downloadCount: 1250
  },
  {
    id: 'toolpath-5axis-machining',
    name: '五轴联动加工',
    description: '创建五轴联动工具路径，适用于复杂曲面加工',
    details: `# 五轴联动加工

## 学习目标
- 理解五轴加工原理
- 掌握刀轴控制策略
- 学习碰撞检测

## 应用场景
- 叶片加工
- 模具型腔精加工
- 叶轮加工
- 医疗植入物

## 刀轴控制策略
- 前倾角控制
- 侧倾角控制
- 点接触/线接触
- 避免奇异点

## 关键技术
1. 刀轴矢量平滑
2. 进给速率优化
3. 碰撞干涉检查
4. 机床运动学仿真`,
    category: 'toolpath',
    difficulty: 'advanced',
    tags: ['五轴', '复杂曲面', 'CNC', '高级'],
    code: `// 五轴加工参数
const fiveAxisParams = {
  machine: '5-axis-vertical',
  toolType: 'ball_nose',
  toolDiameter: 8,
  leadAngle: 15,          // 前倾角（度）
  tiltAngle: 0,           // 侧倾角（度）
  contactType: 'point',   // 点接触
  maxScallop: 0.05        // 最大残留高度 mm
};

// 选择加工面
const surface = selectSurface(model, 'complex_surface');

// 生成五轴工具路径
const toolpath = await generate5AxisToolpath(surface, {
  ...fiveAxisParams,
  strategy: 'flowline',   // 流线加工
  collisionCheck: true,
  axisSmoothing: true
});

// 机床运动学仿真
const machineSim = new MachineSimulation({
  machineModel: 'dmu50',
  toolpath: toolpath,
  workpiece: model
});

const simResult = await machineSim.run();

// 检查碰撞
if (simResult.hasCollision) {
  // 处理碰撞情况
} else {
  exportGCode(toolpath, '5axis_part.nc');
}`,
    language: 'typescript',
    useCases: [
      '航空叶片精密加工',
      '汽车覆盖件模具',
      '医疗植入物加工',
      '叶轮叶盘加工'
    ],
    createdAt: '2024-02-15',
    updatedAt: '2024-03-30',
    downloadCount: 670
  },
  {
    id: 'simulation-force-prediction',
    name: '切削力预测仿真',
    description: '预测切削力大小，优化切削参数避免刀具破损',
    details: `# 切削力预测仿真

## 学习目标
- 理解切削力产生机理
- 掌握切削力预测方法
- 学习参数优化

## 应用场景
- 粗加工参数优化
- 刀具选型
- 机床功率校核
- 颤振预测

## 切削力组成
- 主切削力 Fc
- 进给力 Ff
- 背向力 Fp

## 影响因素
- 工件材料
- 刀具几何参数
- 切削用量
- 冷却条件`,
    category: 'simulation',
    difficulty: 'intermediate',
    tags: ['仿真', '切削力', '优化'],
    code: `// 定义工件材料
const workpieceMaterial = {
  name: 'Ti6Al4V',
  hardness: 36,           // HRC
  tensileStrength: 950,   // MPa
  thermalConductivity: 7  // W/(m·K)
};

// 定义刀具参数
const toolParams = {
  type: 'end_mill',
  diameter: 12,
  fluteCount: 4,
  rakeAngle: 10,
  coating: 'TiAlN'
};

// 定义切削参数
const cuttingParams = {
  cuttingSpeed: 80,       // m/min
  feedPerTooth: 0.1,      // mm/tooth
  axialDepth: 6,          // mm
  radialDepth: 8          // mm
};

// 创建切削力预测模型
const forceModel = new CuttingForceModel({
  material: workpieceMaterial,
  tool: toolParams,
  cutting: cuttingParams
});

// 预测切削力
const forces = forceModel.predict();

// 校核机床功率
const requiredPower = forces.powerRequirement;

// 判断是否安全
if (forces.maxStress > toolParams.allowableStress) {
  // 切削力过大，建议降低切深或进给
}`,
    language: 'typescript',
    useCases: [
      '难加工材料粗加工优化',
      '刀具寿命预测',
      '机床功率校核',
      '颤振稳定性分析'
    ],
    createdAt: '2024-02-08',
    updatedAt: '2024-03-18',
    downloadCount: 950
  },
  {
    id: 'ai-process-planning',
    name: 'AI工艺路线生成',
    description: '基于AI自动生成零件加工工艺路线',
    details: `# AI工艺路线生成

## 学习目标
- 理解工艺规划原理
- 掌握AI工艺生成流程
- 学习工艺优化方法

## 应用场景
- 新产品工艺设计
- 工艺标准化
- 工艺知识复用

## AI工作流程
1. 特征识别与提取
2. 加工方法选择
3. 工序排序优化
4. 切削参数推荐
5. 工艺路线评估

## 输出内容
- 工序卡片
- 刀具清单
- 切削参数表
- 工时估算`,
    category: 'ai',
    difficulty: 'advanced',
    tags: ['AI', '工艺规划', '自动化'],
    code: `// 加载零件模型
const part = await loadModel('bracket.step');

// 初始化AI工艺规划器
const processPlanner = new AIProcessPlanner({
  modelPath: 'models/process_planning_v3.pth',
  factoryCapabilities: {
    machines: ['cnc_mill_3axis', 'cnc_lathe', 'cnc_grinder'],
    tools: 'tool_database.json',
    materials: 'material_database.json'
  }
});

// 生成工艺路线
const processPlan = await processPlanner.generate(part, {
  quality: 'standard',    // standard/high/ultra
  batchSize: 100,
  optimization: 'cost'    // cost/time/quality
});

// 输出工艺路线
processPlan.operations.forEach((op, index) => {
  // 工序信息：名称、设备、刀具、工时
});

// 总工时估算
const totalTime = processPlan.totalTime;
const totalCost = processPlan.totalCost;

// 导出工艺卡片
exportProcessPlan(processPlan, 'bracket_process_plan.pdf');`,
    language: 'typescript',
    useCases: [
      '新产品工艺快速设计',
      '工艺标准化建设',
      '工艺知识库构建',
      '报价快速估算'
    ],
    createdAt: '2024-02-20',
    updatedAt: '2024-04-01',
    downloadCount: 1420
  },
  {
    id: 'basic-parametric-design',
    name: '参数化设计',
    description: '使用参数驱动模型设计，实现快速变型',
    details: `# 参数化设计

## 学习目标
- 理解参数化设计原理
- 掌握参数定义方法
- 学习参数关联关系

## 应用场景
- 系列化产品设计
- 快速变型设计
- 设计自动化

## 参数类型
- 尺寸参数（长宽高）
- 形状参数（圆角半径）
- 位置参数（孔位坐标）
- 材料参数

## 设计流程
1. 定义设计参数
2. 建立参数关联
3. 创建参数化模型
4. 参数驱动更新`,
    category: 'modeling',
    difficulty: 'intermediate',
    tags: ['参数化', '设计', '自动化'],
    code: `// 定义设计参数
const designParams = {
  length: 100,      // mm
  width: 50,        // mm
  height: 30,       // mm
  holeDiameter: 10, // mm
  filletRadius: 5,  // mm
  wallThickness: 3  // mm
};

// 创建参数化模型
const parametricModel = new ParametricModel({
  base: 'box',
  params: designParams,
  constraints: [
    { type: 'min', param: 'length', value: 50 },
    { type: 'max', param: 'length', value: 200 },
    { type: 'ratio', param1: 'width', param2: 'length', value: 0.5 }
  ]
});

// 生成初始模型
const model1 = parametricModel.generate();

// 修改参数，快速变型
designParams.length = 150;
designParams.width = 75;
const model2 = parametricModel.generate();

// 批量生成系列化产品
const variants = [];
for (let i = 0; i < 5; i++) {
  const scale = 1 + i * 0.2;
  const variant = parametricModel.generate({
    length: 100 * scale,
    width: 50 * scale,
    height: 30 * scale
  });
  variants.push(variant);
}`,
    language: 'typescript',
    useCases: [
      '系列化产品设计',
      '快速报价变型',
      '设计自动化',
      '参数化标准件库'
    ],
    createdAt: '2024-02-12',
    updatedAt: '2024-03-25',
    downloadCount: 1080
  },
  {
    id: 'toolpath-hole-machining',
    name: '孔系加工路径',
    description: '自动生成孔系加工工具路径，支持钻、扩、铰、镗',
    details: `# 孔系加工路径

## 学习目标
- 掌握孔加工方法选择
- 学习孔系路径优化
- 理解孔加工参数

## 应用场景
- 箱体类零件
- 法兰盘类零件
- 模具顶针孔

## 孔加工方法
- 钻孔：IT12-IT11
- 扩孔：IT10-IT9
- 铰孔：IT8-IT7
- 镗孔：IT7-IT6

## 路径优化策略
1. 最短路径规划
2. 换刀次数最少
3. 避免空行程`,
    category: 'toolpath',
    difficulty: 'beginner',
    tags: ['孔加工', '工具路径', '自动化', '刀具'],
    code: `// 定义孔特征
const holes = [
  { id: 'H1', type: 'through', diameter: 10, depth: 20, position: [20, 30] },
  { id: 'H2', type: 'through', diameter: 10, depth: 20, position: [80, 30] },
  { id: 'H3', type: 'blind', diameter: 15, depth: 15, position: [50, 60] },
  { id: 'H4', type: 'threaded', diameter: 8, pitch: 1.25, depth: 12, position: [50, 20] }
];

// 定义加工策略
const machiningStrategy = {
  '10': ['drill', 'ream'],           // Φ10孔：钻+铰
  '15': ['drill', 'expand', 'bore'], // Φ15孔：钻+扩+镗
  '8_threaded': ['drill', 'tap']     // 螺纹孔：钻+攻丝
};

// 生成孔系加工路径
const holeToolpath = await generateHoleToolpath(holes, {
  strategy: machiningStrategy,
  optimization: 'shortest_path',
  toolChangeMinimize: true
});

// 输出加工顺序
holeToolpath.operations.forEach((op, index) => {
  // 加工步骤：操作类型、孔ID、刀具、参数
});

// 导出G代码
exportGCode(holeToolpath, 'hole_machining.nc');`,
    language: 'typescript',
    useCases: [
      '箱体类零件孔系加工',
      '法兰盘孔加工',
      '模具顶针孔加工',
      '自动化孔加工程序生成'
    ],
    createdAt: '2024-02-18',
    updatedAt: '2024-03-20',
    downloadCount: 1890
  },
  {
    id: 'advanced-lattice-structure',
    name: '点阵结构设计',
    description: '创建轻量化点阵结构，用于3D打印和轻量化设计',
    details: `# 点阵结构设计

## 学习目标
- 理解点阵结构原理
- 掌握点阵类型
- 学习轻量化设计

## 应用场景
- 航空航天轻量化
- 3D打印支撑结构
- 吸能缓冲结构
- 散热结构

## 点阵类型
- 简单立方
- 体心立方
- 面心立方
- 八桁架
- 吉伯点阵

## 设计参数
- 胞元尺寸
- 支柱直径
- 相对密度
- 孔隙率`,
    category: 'advanced',
    difficulty: 'advanced',
    tags: ['点阵', '轻量化', '3D打印'],
    code: `// 定义点阵参数
const latticeParams = {
  type: 'octet_truss',      // 八桁架点阵
  cellSize: 5,              // 胞元尺寸 mm
  strutDiameter: 1,         // 支柱直径 mm
  relativeDensity: 0.15,    // 相对密度
  gradient: true            // 梯度点阵
};

// 定义填充区域
const fillRegion = {
  type: 'box',
  min: [0, 0, 0],
  max: [100, 50, 30]
};

// 创建点阵结构
const lattice = new LatticeStructure({
  params: latticeParams,
  region: fillRegion,
  gradient: {
    direction: 'z',
    densityStart: 0.1,
    densityEnd: 0.3
  }
});

// 生成点阵几何
const latticeGeometry = lattice.generate();

// 力学性能预测
const mechanicalProps = lattice.predictProperties();

// 与实心对比
const solidWeight = 100 * 50 * 30 * 7.8e-3; // 钢的密度
const weightReduction = ((1 - mechanicalProps.weight / solidWeight) * 100).toFixed(1);

// 导出为STL（3D打印）
exportSTL(latticeGeometry, 'lattice_structure.stl');`,
    language: 'typescript',
    useCases: [
      '航空航天轻量化设计',
      '3D打印支撑结构',
      '吸能缓冲装置',
      '高效散热结构'
    ],
    createdAt: '2024-03-01',
    updatedAt: '2024-04-05',
    downloadCount: 520
  },
  {
    id: 'simulation-chatter-prediction',
    name: '颤振稳定性预测',
    description: '预测加工过程颤振，优化切削参数避免振动',
    details: `# 颤振稳定性预测

## 学习目标
- 理解颤振产生机理
- 掌握稳定性叶瓣图
- 学习稳定切削参数选择

## 应用场景
- 高速加工优化
- 细长轴加工
- 薄壁件加工
- 刀具寿命提升

## 颤振类型
- 再生颤振
- 模态耦合颤振
- 摩擦颤振

## 稳定性叶瓣图
通过稳定性叶瓣图，选择稳定的切削参数组合，避免颤振发生。`,
    category: 'simulation',
    difficulty: 'advanced',
    tags: ['仿真', '颤振', '稳定性'],
    code: `// 定义机床-刀具系统参数
const systemParams = {
  modalMass: 2.5,           // kg
  modalDamping: 0.05,       // 阻尼比
  modalStiffness: 1e6,      // N/m
  naturalFrequency: 100,    // Hz
  toolOverhang: 80,         // mm
  toolDiameter: 12          // mm
};

// 定义工件材料
const materialParams = {
  name: 'Al6061',
  specificCuttingForce: 800, // MPa
  cuttingForceCoeff: 1.0
};

// 创建颤振预测模型
const chatterModel = new ChatterPredictionModel({
  system: systemParams,
  material: materialParams,
  fluteCount: 4
});

// 生成稳定性叶瓣图
const stabilityLobe = chatterModel.generateStabilityLobe({
  speedRange: [1000, 10000],  // rpm
  depthRange: [0.1, 10],      // mm
  resolution: 100
});

// 推荐稳定参数
const stableParams = stabilityLobe.recommendStableParameters({
  targetDepth: 5,
  preferredSpeed: 6000
});

// 可视化稳定性叶瓣图
stabilityLobe.plot('stability_lobe.png');`,
    language: 'typescript',
    useCases: [
      '高速加工参数优化',
      '细长轴加工防颤',
      '薄壁件加工稳定性',
      '刀具悬伸优化'
    ],
    createdAt: '2024-03-05',
    updatedAt: '2024-04-08',
    downloadCount: 430
  }
];

/**
 * 获取所有分类
 */
export function getCategories(): { value: string; label: string }[] {
  return [
    { value: 'all', label: '全部分类' },
    { value: 'basic', label: '基础示例' },
    { value: 'modeling', label: '3D建模' },
    { value: 'toolpath', label: '工具路径' },
    { value: 'simulation', label: '仿真模拟' },
    { value: 'ai', label: 'AI功能' },
    { value: 'advanced', label: '高级应用' }
  ];
}

/**
 * 获取所有难度级别
 */
export function getDifficulties(): { value: string; label: string }[] {
  return [
    { value: 'all', label: '全部难度' },
    { value: 'beginner', label: '入门' },
    { value: 'intermediate', label: '中级' },
    { value: 'advanced', label: '高级' }
  ];
}

/**
 * 获取所有标签
 */
export function getAllTags(): string[] {
  const tags = new Set<string>();
  exampleProjects.forEach(project => {
    project.tags.forEach(tag => tags.add(tag));
  });
  return Array.from(tags).sort();
}
