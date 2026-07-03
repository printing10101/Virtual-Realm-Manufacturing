# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "views", "UXDemo.vue")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

sq = chr(39)

# Add useI18n import
old_import = "import { ref, computed, onMounted } from " + sq + "vue" + sq
new_import = old_import + "\nimport { useI18n } from " + sq + "vue-i18n" + sq
if old_import in text and "useI18n" not in text:
    text = text.replace(old_import, new_import)
    print("Added useI18n import")

# Add const { t } = useI18n() after ElMessage import
old_elm = "import { ElMessage } from " + sq + "element-plus" + sq
new_elm = old_elm + "\n\nconst { t } = useI18n()"
if old_elm in text and "const { t } = useI18n()" not in text:
    text = text.replace(old_elm, new_elm)
    print("Added const { t } = useI18n()")

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Script imports done")
