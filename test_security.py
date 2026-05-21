import sys, os
import importlib

# Clean up environment before first import
os.environ.pop('ENV', None)
os.environ.pop('LNN_JWT_SECRET', None)

# Ensure the python directory is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

# A valid secret that passes randomness checks (generated securely)
_VALID_SECRET = "xK9mP2nQ7rS5tU3vW1yZ4aB6cD8eF0gH"  # 32 chars, diverse chars


def reload_security_module():
    """Properly reload the security module with fresh environment"""
    # Remove the module from cache to force reimport
    modules_to_remove = [m for m in sys.modules if m.startswith('app.core.security')]
    for m in modules_to_remove:
        del sys.modules[m]
    
    import app.core.security as sec
    importlib.reload(sec)
    return sec


def test_no_secret_all_envs_fail():
    """所有环境未设置 LNN_JWT_SECRET - 应该失败"""
    os.environ.pop('LNN_JWT_SECRET', None)
    os.environ.pop('ENV', None)

    try:
        sec = reload_security_module()
        print('FAIL: 未设置密钥应该拒绝启动')
        return False
    except RuntimeError as e:
        err_msg = str(e)
        if ('LNN_JWT_SECRET' in err_msg and
            'secrets.token_urlsafe' in err_msg and
            '拒绝启动' in err_msg):
            print('PASS: 未设置密钥 - 正确拒绝启动并包含生成指导')
            return True
        else:
            print(f'FAIL: 错误信息不完整: {e}')
            return False
    except Exception as e:
        print(f'FAIL: 异常类型不正确: {type(e).__name__}: {e}')
        return False


def test_short_secret():
    """设置长度不足32字符的密钥 - 应该失败"""
    os.environ['LNN_JWT_SECRET'] = 'short-key'

    try:
        sec = reload_security_module()
        print('FAIL: 密钥长度不足应该拒绝启动')
        return False
    except ValueError as e:
        err_msg = str(e)
        if ('长度不足' in err_msg and
            'secrets.token_urlsafe' in err_msg):
            print('PASS: 密钥长度不足 - 正确拒绝启动并包含生成指导')
            return True
        else:
            print(f'FAIL: 错误信息不完整: {e}')
            return False
    except Exception as e:
        print(f'FAIL: 异常类型不正确: {type(e).__name__}: {e}')
        return False


def test_insecure_secret_same_char():
    """设置全相同字符的密钥 - 应该失败"""
    os.environ['LNN_JWT_SECRET'] = 'a' * 40

    try:
        sec = reload_security_module()
        print('FAIL: 全相同字符密钥应该拒绝启动')
        return False
    except ValueError as e:
        if '安全性不足' in str(e) and '全相同字符' in str(e):
            print('PASS: 全相同字符密钥 - 正确拒绝启动')
            return True
        else:
            print(f'FAIL: 错误信息不正确: {e}')
            return False
    except Exception as e:
        print(f'FAIL: 异常类型不正确: {type(e).__name__}: {e}')
        return False


def test_insecure_secret_few_chars():
    """设置字符种类过少的密钥 - 应该失败"""
    os.environ['LNN_JWT_SECRET'] = 'ab' * 20  # only 2 unique chars, 40 chars total

    try:
        sec = reload_security_module()
        print('FAIL: 字符种类过少的密钥应该拒绝启动')
        return False
    except ValueError as e:
        if '安全性不足' in str(e) and '随机性不足' in str(e):
            print('PASS: 字符种类过少的密钥 - 正确拒绝启动')
            return True
        else:
            print(f'FAIL: 错误信息不正确: {e}')
            return False
    except Exception as e:
        print(f'FAIL: 异常类型不正确: {type(e).__name__}: {e}')
        return False


def test_insecure_secret_repeating_pattern():
    """设置简单重复模式的密钥 - 应该失败"""
    os.environ['LNN_JWT_SECRET'] = 'abcd' * 10  # repeating pattern

    try:
        sec = reload_security_module()
        print('FAIL: 简单重复模式密钥应该拒绝启动')
        return False
    except ValueError as e:
        if '安全性不足' in str(e) and '重复模式' in str(e):
            print('PASS: 简单重复模式密钥 - 正确拒绝启动')
            return True
        else:
            print(f'FAIL: 错误信息不正确: {e}')
            return False
    except Exception as e:
        print(f'FAIL: 异常类型不正确: {type(e).__name__}: {e}')
        return False


def test_valid_secret_loads():
    """设置有效密钥 - 应该成功加载"""
    os.environ['LNN_JWT_SECRET'] = _VALID_SECRET

    try:
        sec = reload_security_module()
        if sec.SECRET_KEY == _VALID_SECRET:
            print('PASS: 有效密钥 - 正确加载且 SECRET_KEY 匹配')
            return True
        else:
            print(f'FAIL: SECRET_KEY 不匹配')
            return False
    except Exception as e:
        print(f'FAIL: 不应该抛出异常: {type(e).__name__}: {e}')
        return False


def test_generate_function():
    """测试 generate_secure_jwt_secret 函数"""
    # First ensure we're in a valid state to import
    os.environ['LNN_JWT_SECRET'] = _VALID_SECRET
    sec = reload_security_module()

    try:
        from app.core.security import generate_secure_jwt_secret

        # Test default length
        secret = generate_secure_jwt_secret()
        if len(secret) >= 32:
            print('PASS: generate_secure_jwt_secret() 生成密钥长度符合要求')
        else:
            print(f'FAIL: 生成密钥长度不足: {len(secret)}')
            return False

        # Test custom length
        secret = generate_secure_jwt_secret(length=48)
        if len(secret) >= 48:
            print('PASS: generate_secure_jwt_secret(length=48) 生成密钥长度符合要求')
        else:
            print(f'FAIL: 自定义长度生成密钥长度不足: {len(secret)}')
            return False

        # Test minimum length enforcement
        try:
            generate_secure_jwt_secret(length=16)
            print('FAIL: 应该拒绝长度<32的请求')
            return False
        except ValueError:
            print('PASS: generate_secure_jwt_secret() 正确拒绝长度<32的请求')
            return True
    except Exception as e:
        print(f'FAIL: 测试过程中出现异常: {type(e).__name__}: {e}')
        return False


if __name__ == '__main__':
    results = []

    print('\n=== 核心安全测试 ===')
    results.append(('未设置密钥所有环境拒绝启动', test_no_secret_all_envs_fail()))
    results.append(('密钥长度不足拒绝启动', test_short_secret()))

    print('\n=== 密钥随机性验证测试 ===')
    results.append(('全相同字符密钥被拒绝', test_insecure_secret_same_char()))
    results.append(('字符种类过少密钥被拒绝', test_insecure_secret_few_chars()))
    results.append(('简单重复模式密钥被拒绝', test_insecure_secret_repeating_pattern()))

    print('\n=== 有效密钥加载测试 ===')
    results.append(('有效密钥正常加载', test_valid_secret_loads()))

    print('\n=== 密钥生成函数测试 ===')
    results.append(('密钥生成函数', test_generate_function()))

    print('\n=== 测试结果汇总 ===')
    all_passed = True
    for name, passed in results:
        status = 'PASS' if passed else 'FAIL'
        print(f'  {name}: {status}')
        if not passed:
            all_passed = False

    if all_passed:
        print('\n所有测试通过!')
        sys.exit(0)
    else:
        print('\n存在失败的测试!')
        sys.exit(1)
