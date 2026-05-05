"""测试数据工厂模块。

使用factory-boy创建测试数据工厂，用于生成各类测试对象，
包括AgentContext、LLM响应、知识库查询结果等。
"""
import json

import factory

from app.ai.agents import AgentContext


class AgentContextFactory(factory.Factory):
    """AgentContext测试数据工厂。

    用于快速创建不同场景下的AgentContext实例，
    支持自定义参数覆盖默认值。

    使用示例:
        # 默认创建
        ctx = AgentContextFactory()

        # 使用Trait预设
        ctx = AgentContextFactory(simple_request=True)
        ctx = AgentContextFactory(complex_request=True)

        # 覆盖默认参数
        ctx = AgentContextFactory(user_input="自定义输入")

    Attributes:
        user_input: 用户输入文本，默认简单制造需求
        extracted_params: 已提取参数字典，默认为空
        process_route: 工艺路线列表，默认为空
        cutting_parameters: 切削参数字典，默认为空
        nc_code: NC代码字符串，默认为空
        verification_result: 验证结果字典，默认为空
        repair_suggestions: 修复建议列表，默认为空
        current_stage: 当前阶段字符串，默认为空
        stage_status: 阶段状态字符串，默认为空
    """

    class Meta:
        model = AgentContext

    user_input = "我需要加工一个45钢的轴类零件，长度100mm"
    extracted_params = factory.Dict({})
    process_route = factory.List([])
    cutting_parameters = factory.Dict({})
    nc_code = ""
    verification_result = factory.Dict({})
    repair_suggestions = factory.List([])
    current_stage = ""
    stage_status = ""

    class Params:
        """工厂参数配置类。

        定义常用的测试场景预设，可通过工厂类方法快速创建。
        """
        simple_request = factory.Trait(
            user_input="加工45钢轴，直径50mm，长度200mm"
        )

        complex_request = factory.Trait(
            user_input="""我需要加工以下零件：1. 6061铝合金壳体，尺寸200x150x100mm，公差IT8，表面粗糙度Ra1.6 2. 45钢传动轴，直径30mm，长度500mm，公差IT6，表面粗糙度Ra0.4 加工数量：各50件"""
        )

        empty_request = factory.Trait(
            user_input=""
        )

        vague_request = factory.Trait(
            user_input="帮我做一个金属零件"
        )

        understood = factory.Trait(
            extracted_params=factory.Dict({
                "material": "45钢",
                "part_type": "轴类零件",
                "dimensions": factory.Dict({"length": 100.0, "width": 50.0, "height": 30.0}),
                "tolerance": "IT7",
                "surface_roughness": "Ra 0.8",
                "quantity": 100
            }),
            current_stage="understanding",
            stage_status="completed"
        )

    @classmethod
    def create_with_json_response(cls):
        """创建带有完整JSON响应格式的AgentContext。

        模拟LLM返回了完整JSON格式参数提取结果的场景。

        Returns:
            AgentContext: 包含提取参数的AgentContext实例
        """
        return cls(
            user_input="加工一批45钢齿轮，模数2，齿数30，精度等级7级",
            extracted_params={
                "material": "45钢",
                "part_type": "齿轮类零件",
                "dimensions": {"module": 2, "teeth_count": 30},
                "tolerance": "7级",
                "surface_roughness": "Ra 1.6",
                "quantity": 200
            },
            current_stage="understanding",
            stage_status="completed"
        )

    @classmethod
    def create_with_partial_params(cls):
        """创建仅包含部分提取参数的AgentContext。

        模拟LLM只返回了部分参数，存在缺失字段的场景。

        Returns:
            AgentContext: 包含部分提取参数的AgentContext实例
        """
        return cls(
            user_input="做一个铝合金的盒子",
            extracted_params={
                "material": "铝合金",
                "part_type": "壳体"
            },
            current_stage="understanding",
            stage_status="completed"
        )

    @classmethod
    def create_with_failed_status(cls):
        """创建understanding阶段失败的AgentContext。

        模拟参数提取失败，仅保存了原始输入的场景。

        Returns:
            AgentContext: 状态为failed的AgentContext实例
        """
        return cls(
            user_input="加工零件",
            extracted_params={"raw_input": "加工零件"},
            current_stage="understanding",
            stage_status="failed: JSON解析错误"
        )


class LLMResponseFactory(factory.Factory):
    """LLM响应测试数据工厂。

    用于快速创建不同格式的LLM响应数据，
    测试JSON解析和容错处理逻辑。

    使用示例:
        # 默认创建 (完整JSON)
        resp = LLMResponseFactory()

        # 使用Trait预设
        resp = LLMResponseFactory(json_only=True)
        resp = LLMResponseFactory(markdown_json=True)

    Attributes:
        content: LLM返回的内容字符串
        model: 使用的模型名称
        finish_reason: 完成原因
    """

    class Meta:
        model = dict

    content = factory.LazyAttribute(
        lambda o: json.dumps({
            "material": "45钢",
            "part_type": "轴类零件",
            "dimensions": {"length": 100.0, "width": 50.0, "height": 30.0},
            "tolerance": "IT7",
            "surface_roughness": "Ra 0.8",
            "quantity": 100
        }, ensure_ascii=False)
    )
    model = "qwen2.5-coder:7b"
    finish_reason = "stop"

    class Params:
        """工厂参数配置类。

        定义不同响应格式的预设。
        """
        json_only = factory.Trait(
            content=factory.LazyAttribute(
                lambda o: json.dumps({"material": "45钢", "part_type": "轴类"}, ensure_ascii=False)
            )
        )

        markdown_json = factory.Trait(
            content=factory.LazyAttribute(
                lambda o: '```json\n' + json.dumps({"material": "6061铝合金", "part_type": "壳体"}, ensure_ascii=False) + '\n```'
            )
        )

        markdown_code_block = factory.Trait(
            content=factory.LazyAttribute(
                lambda o: '```\n' + json.dumps({"material": "45钢", "part_type": "齿轮"}, ensure_ascii=False) + '\n```'
            )
        )

        plain_text = factory.Trait(
            content="根据分析，材料为45钢，零件类型为轴类零件"
        )

        empty = factory.Trait(
            content=""
        )

        invalid_json = factory.Trait(
            content='{"material": "45钢", "part_type": }'
        )

        json_with_text = factory.Trait(
            content=factory.LazyAttribute(
                lambda o: '好的，我来分析您的需求。\n\n' +
                          '```json\n' +
                          json.dumps({"material": "45钢"}, ensure_ascii=False) +
                          '\n```\n\n以上就是分析结果。'
            )
        )


class KnowledgeQueryResultFactory(factory.Factory):
    """知识库查询结果测试数据工厂。

    用于快速创建RAG检索结果数据，
    测试知识增强检索逻辑。

    使用示例:
        # 默认创建 (多条结果)
        result = KnowledgeQueryResultFactory()

        # 使用Trait预设
        result = KnowledgeQueryResultFactory(empty=True)
        result = KnowledgeQueryResultFactory(single_result=True)

    Attributes:
        documents: 检索到的文档列表
        metadatas: 对应的元数据列表
        distances: 相似度距离列表
        ids: 文档ID列表
    """

    class Meta:
        model = dict

    documents = factory.List([
        "车削加工基础：车削是最基本的金属切削加工方法。",
        "45钢材料参数：45钢是中碳结构钢，抗拉强度≥600MPa。"
    ])
    metadatas = factory.List([
        {"type": "车削", "category": "加工工艺"},
        {"type": "材料", "category": "45钢"}
    ])
    distances = factory.List([0.1, 0.2])
    ids = factory.List(["turning_basic", "steel_45"])

    class Params:
        """工厂参数配置类。

        定义不同查询结果的预设。
        """
        empty = factory.Trait(
            documents=factory.List([]),
            metadatas=factory.List([]),
            distances=factory.List([]),
            ids=factory.List([])
        )

        single_result = factory.Trait(
            documents=factory.List(["车削加工基础：车削是最基本的金属切削加工方法。"]),
            metadatas=factory.List([{"type": "车削", "category": "加工工艺"}]),
            distances=factory.List([0.1]),
            ids=factory.List(["turning_basic"])
        )

        multiple_results = factory.Trait(
            documents=factory.List([
                "车削加工基础：车削是最基本的金属切削加工方法。",
                "45钢材料参数：45钢是中碳结构钢。",
                "表面粗糙度等级：Ra 0.8属于半精加工级别。",
                "IT公差等级：IT7用于一般精密配合。",
                "铣削加工基础：铣削主要用于加工平面和沟槽。"
            ]),
            metadatas=factory.List([
                {"type": "车削", "category": "加工工艺"},
                {"type": "材料", "category": "45钢"},
                {"type": "标准", "category": "表面粗糙度"},
                {"type": "标准", "category": "公差等级"},
                {"type": "铣削", "category": "加工工艺"}
            ]),
            distances=factory.List([0.05, 0.1, 0.15, 0.2, 0.25]),
            ids=factory.List(["turning_basic", "steel_45", "surface_roughness", "it_tolerance", "milling_basic"])
        )
