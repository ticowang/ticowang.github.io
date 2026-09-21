# -*- coding: utf-8 -*-
"""
gfex-site 构建脚本
把 _src/ 下的模板片段与 data.json 拼装成最终交付文件：
  index.html  <- _src/head.html + _src/app.js(注入 EMBEDDED_DATA) + _src/tail.html
  admin.html  <- _src/admin.html + _src/admin.js + _src/tail_admin.html

用法：更新数据后重新运行  python build.py
"""
import json
import io
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with io.open(os.path.join(BASE, name), "r", encoding="utf-8") as f:
        return f.read()


def write(name, text):
    with io.open(os.path.join(BASE, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    # ---- index.html ----
    data = json.loads(read("data.json"))
    emb = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    emb = emb.replace("</", "<\\/")  # 防止 </script> 提前闭合
    head = read(os.path.join("_src", "head.html"))
    app = read(os.path.join("_src", "app1.js")) + "\n" + read(os.path.join("_src", "app2.js"))
    tail = read(os.path.join("_src", "tail.html"))
    assert "/*__EMBEDDED_DATA__*/" in app, "app.js 缺少嵌入占位符"
    app = app.replace("/*__EMBEDDED_DATA__*/", emb)
    write("index.html", head + app + tail)

    # ---- admin.html ----
    admin_html = read(os.path.join("_src", "admin.html"))
    admin_js = read(os.path.join("_src", "admin.js"))
    tail_admin = read(os.path.join("_src", "tail_admin.html"))
    write("admin.html", admin_html + admin_js + tail_admin)

    print("build ok  index.html=%d bytes  admin.html=%d bytes" %
          (len(head + app + tail), len(admin_html + admin_js + tail_admin)))


if __name__ == "__main__":
    main()
