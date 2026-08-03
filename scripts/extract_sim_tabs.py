import re

path = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\src\views\Simulation.vue"
src = open(path, 'r', encoding='utf-8').read()

# Extract sections
# Tab 1: lines 122-527 (template block)
# Tab 2: lines 530-710
# Tab 3: lines 713-943

lines = src.split('\n')

# Find exact section boundaries
def find_section(start_marker, end_marker):
    """Find section from start_marker to end_marker in source text, return (content, start_idx, end_idx)"""
    s = src.index(start_marker)
    e = src.index(end_marker, s) + len(end_marker)
    return src[s:e], s, e

# Tab 1: from Tab 1 comment to Tab 2 comment
tab1_content, t1s, t1e = find_section(
    '    <!-- Tab 1: NC Code Simulation -->\n    <div\n      v-show="activeTab === \'simulation\'"',
    '    <!-- Tab 2: FEM Analysis -->'
)
# Trim trailing newlines
tab1_content = tab1_content.rstrip('\n')

# Tab 2: from Tab 2 comment to Tab 3 comment
tab2_content, t2s, t2e = find_section(
    '    <!-- Tab 2: FEM Analysis -->\n    <div\n      v-show="activeTab === \'fem\'"',
    '    <!-- Tab 3: Export Management -->'
)
tab2_content = tab2_content.rstrip('\n')

# Tab 3: from Tab 3 comment to template end
tab3_start = '    <!-- Tab 3: Export Management -->\n    <div\n      v-show="activeTab === \'export\'"'
tab3_end = '  </div>\n</template>'
s3 = src.index(tab3_start)
e3 = src.index(tab3_end, s3)
tab3_content = src[s3:e3]

# Also extract CollisionAlertModal usage in tab 3 (line 938-943)
post_tab3 = src[e3:e3+100]  # check what follows

print(f"Tab1: {len(tab1_content.splitlines())} lines")
print(f"Tab2: {len(tab2_content.splitlines())} lines")
print(f"Tab3: {len(tab3_content.splitlines())} lines")
print(f"Tab1 pos: {t1s}-{t1e}")
print(f"Tab3 end pos: {e3}")
print("OK - sections extracted")
