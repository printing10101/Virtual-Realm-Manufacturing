"""
测试用例生成器

基于代码分析结果自动生成 pytest 测试文件
"""

import os
from pathlib import Path
from datetime import datetime
from .analyzer import CodeAnalyzer, ModuleInfo, FunctionInfo, ClassInfo


class TestGenerator:
    """测试用例生成器"""

    def __init__(self, output_dir: str | Path = "tests/generated"):
        self.output_dir = Path(output_dir)

    def generate_for_module(self, module_info: ModuleInfo) -> Path | None:
        """为单个模块生成测试文件"""
        testable = self._get_testable_items(module_info)
        if not testable['functions'] and not testable['classes']:
            return None

        lines = [
            f'"""',
            f'自动生成的测试文件 - {module_info.name}',
            f'生成时间: {datetime.now().isoformat()}',
            f'"""',
            f'',
            f'import pytest',
        ]

        # 尝试生成导入语句
        import_path = module_info.name.replace('.', '/')
        module_import = module_info.name
        lines.append(f'')
        lines.append(f'# 注意: 请根据实际项目结构调整导入路径')
        lines.append(f'# from {module_import} import ...')
        lines.append(f'')

        # 为函数生成测试
        for func in testable['functions']:
            lines.extend(self._generate_function_test(func, module_import))

        # 为类生成测试
        for cls in testable['classes']:
            lines.extend(self._generate_class_test(cls, module_import))

        # 写入文件
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = module_info.name.replace('.', '_')
        test_file = self.output_dir / f"test_{safe_name}.py"
        test_file.write_text('\n'.join(lines), encoding='utf-8')
        return test_file

    def generate_for_directory(self, source_dir: str | Path) -> list[Path]:
        """为目录中所有模块生成测试文件"""
        analyzer = CodeAnalyzer(source_dir)
        modules = analyzer.analyze_directory()
        generated = []
        for mod in modules:
            result = self.generate_for_module(mod)
            if result:
                generated.append(result)
        return generated

    def _get_testable_items(self, module_info: ModuleInfo) -> dict:
        """获取可测试的项目"""
        testable = {'functions': [], 'classes': []}
        for func in module_info.functions:
            if not func.name.startswith('_'):
                testable['functions'].append(func)
        for cls in module_info.classes:
            if not cls.name.startswith('_'):
                public_methods = [
                    m for m in cls.methods
                    if not m.name.startswith('_') or m.name.startswith('__')
                ]
                if public_methods:
                    cls_copy = ClassInfo(
                        name=cls.name, module=cls.module,
                        lineno=cls.lineno, bases=cls.bases,
                        methods=public_methods, docstring=cls.docstring
                    )
                    testable['classes'].append(cls_copy)
        return testable

    def _generate_function_test(self, func: FunctionInfo, module_import: str) -> list[str]:
        """为函数生成测试代码"""
        lines = [
            f'',
            f'class Test_{func.name}:',
            f'    """测试 {func.name} 函数"""',
            f'',
        ]

        # 生成正常路径测试
        lines.extend([
            f'    def test_{func.name}_normal(self):',
            f'        """正常路径测试"""',
            f'        # TODO: 根据实际函数签名填入参数',
        ])

        if func.args:
            args_str = ', '.join(f'{a}=None' for a in func.args)
            lines.append(f'        # result = {func.name}({args_str})')
            lines.append(f'        # assert result is not None')
        else:
            lines.append(f'        # result = {func.name}()')
            lines.append(f'        # assert result is not None')

        lines.append(f'        pytest.skip("TODO: implement test")')
        lines.append(f'')

        # 生成边界测试
        lines.extend([
            f'    def test_{func.name}_edge_cases(self):',
            f'        """边界条件测试"""',
            f'        # TODO: 测试空值、极值等边界情况',
            f'        pytest.skip("TODO: implement edge case tests")',
            f'',
        ])

        # 如果是异步函数，添加异步测试
        if func.is_async:
            lines.extend([
                f'    @pytest.mark.asyncio',
                f'    async def test_{func.name}_async(self):',
                f'        """异步调用测试"""',
                f'        # TODO: 使用 pytest-asyncio 测试异步行为',
                f'        pytest.skip("TODO: implement async test")',
                f'',
            ])

        return lines

    def _generate_class_test(self, cls: ClassInfo, module_import: str) -> list[str]:
        """为类生成测试代码"""
        lines = [
            f'',
            f'class Test_{cls.name}:',
            f'    """测试 {cls.name} 类"""',
            f'',
            f'    @pytest.fixture',
            f'    def instance(self):',
            f'        """创建测试实例"""',
            f'        # TODO: 根据实际构造函数填入参数',
            f'        # return {cls.name}()',
            f'        pytest.skip("TODO: create instance")',
            f'',
        ]

        # 为每个公开方法生成测试
        for method in cls.methods:
            if method.name.startswith('__') and method.name != '__init__':
                continue
            if method.name == '__init__':
                continue

            lines.extend([
                f'    def test_{method.name}(self, instance):',
                f'        """测试 {method.name} 方法"""',
                f'        # TODO: 调用方法并验证结果',
                f'        # result = instance.{method.name}()',
                f'        # assert result is not None',
                f'        pytest.skip("TODO: implement test")',
                f'',
            ])

        return lines
