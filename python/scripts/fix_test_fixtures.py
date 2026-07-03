"""修复测试文件中的 fixture 调用问题。

将所有 self.make_processor() 调用改为使用 fixture 参数，
并在对应的方法签名中添加 make_processor 参数。
"""
import re
from pathlib import Path


def fix_test_file(file_path: str) -> None:
    """修复测试文件中的 fixture 调用。"""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    
    # 步骤 1: 替换所有 self.make_processor() 为 make_processor()
    content = content.replace("self.make_processor()", "make_processor()")
    
    # 步骤 2: 找到所有包含 make_processor() 调用的测试方法，添加 fixture 参数
    # 匹配模式: def test_xxx(self): 或 def test_xxx(self, xxx):
    lines = content.split("\n")
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # 检查是否是测试方法定义
        if re.match(r"^\s+def test_\w+\(self", line):
            # 检查接下来的几行是否包含 make_processor() 调用
            has_make_processor = False
            for j in range(i + 1, min(i + 20, len(lines))):
                if "make_processor()" in lines[j]:
                    has_make_processor = True
                    break
                # 如果遇到下一个方法定义，停止检查
                if re.match(r"^\s+def ", lines[j]):
                    break
            
            # 如果包含 make_processor() 调用，检查方法签名是否已有该参数
            if has_make_processor and "make_processor" not in line:
                # 在方法签名中添加 make_processor 参数
                # 处理不同的签名格式
                if "(self):" in line:
                    line = line.replace("(self):", "(self, make_processor):")
                elif "(self, " in line:
                    # 已经有其他参数，在 self 后面添加
                    line = line.replace("(self, ", "(self, make_processor, ")
                new_lines[-1] = line
        
        i += 1
    
    # 写回文件
    path.write_text("\n".join(new_lines), encoding="utf-8")
    print(f"✓ 已修复 {file_path}")


if __name__ == "__main__":
    test_file = r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\tests\test_postprocessor.py"
    fix_test_file(test_file)
