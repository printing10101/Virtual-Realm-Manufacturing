#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def replace_in_file(path, replacements):
    content = read_file(path)
    count = 0
    for old, new in replacements:
        if old not in content:
            print(f"  WARNING: not found: {repr(old[:60])}")
            continue
        content = content.replace(old, new, 1)
        count += 1
    write_file(path, content)
    print(f"  Modified: {path} ({count} replacements)")
    return count

def add_namespace_to_locale(locale_path, namespace_content):
    content = read_file(locale_path)
    idx = content.rstrip().rfind('\n}')
    if idx == -1:
        print(f"  ERROR: pattern not found: {locale_path}")
        return False
    insert_pos = idx + 1
    new_content = content[:insert_pos] + namespace_content + ',\n' + content[insert_pos:]
    write_file(locale_path, new_content)
    print(f"  Added namespace to: {locale_path}")
    return True

if __name__ == '__main__':
    print("i18n helper ready")
