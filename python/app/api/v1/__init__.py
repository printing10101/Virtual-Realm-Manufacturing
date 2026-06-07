from app.api.v1 import (  # noqa: F401
    lnn,
    jobs,
    plugins,  # TODO: 实验性模块 - 市场/日志查询为桩代码，待完整实现后注册路由
    skills,
    sse,
    agent_gateway,
    cost_budget,
    governance,
    goal_alignment,
    heartbeat,
    wear_prediction,
    user_sovereignty,
    task_checkout,
    template_ab_testing_routes,
    template_branching_routes,
    template_evolution_routes,
    template_market,  # TODO: 实验性模块 - 使用内存存储无持久化，待接入数据库后注册路由
    template_update_routes,
    pattern_engine_routes,
)
