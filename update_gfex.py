# -*- coding: utf-8 -*-
"""广期所仓单日报 · 自动抓取脚本

从广州期货交易所官网接口抓取最新交易日（或指定交易日）的仓单数据，
生成 data.json / days-YYYY.json，并重新构建内嵌最新数据的 index.html。

用法：
  python update_gfex.py                  # 自动探测并抓取最新交易日
  python update_gfex.py --date 20260921  # 抓取指定交易日（yyyyMMdd）
  python update_gfex.py --dry-run        # 只探测与计算，不写文件

本脚本只用 Python 标准库，无需安装任何依赖。
"""
import datetime
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API_URL = "http://www.gfex.com.cn/u/interfacesWebTdWbillWeeklyQuotes/loadList"
VARIETIES = [("lc", "碳酸锂", "LC"), ("ps", "多晶硅", "PS"), ("si", "工业硅", "SI")]
SOURCE = "广州期货交易所 仓单日报（官网接口 http://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml）"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
LOG_FILE = os.path.join(BASE, "update_log.txt")


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def api_get(gen_date, variety):
    """POST 官网仓单日报接口，返回 JSON。"""
    body = urllib.parse.urlencode({"gen_date": gen_date, "variety": variety}).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe_date(gen_date):
    """用 lc 品种探测某日是否有数据（1 次请求）。"""
    try:
        j = api_get(gen_date, "lc")
    except Exception:
        return False
    for r in (j.get("data") or []):
        if not r.get("whAbbr") and r.get("variety") == "总计":
            return r.get("wbillQty") is not None
    return False


def fetch_day(gen_date):
    """抓取某日三个品种的仓单明细，返回 {code: {name,code,total,rows}}。"""
    out = {}
    for code, name, ccode in VARIETIES:
        j = api_get(gen_date, code)
        data = j.get("data") or []
        rows = [r for r in data if r.get("whAbbr")]
        total = None
        for r in data:
            if not r.get("whAbbr") and r.get("variety") == "总计":
                total = (r.get("lastWbillQty"), r.get("wbillQty"), r.get("diff"))
                break
        out[code] = {"name": name, "code": ccode, "total": total, "rows": rows}
    return out


def find_latest(limit=45):
    """从今天往回找最近一个已公布数据的交易日。"""
    today = datetime.date.today()
    for i in range(limit):
        gd = (today - datetime.timedelta(days=i)).strftime("%Y%m%d")
        if probe_date(gd):
            return gd
    return None


def read_json(name):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(name, obj):
    with open(os.path.join(BASE, name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def fmt_date(gd):
    return "%s-%s-%s" % (gd[0:4], gd[4:6], gd[6:8])


def local_total(code, date_str):
    """从本地 data.json / days-*.json 取某日某品种的今日仓单总量。"""
    if date_str is None:
        return None
    data = read_json("data.json")
    if data and data.get("data_date") == date_str:
        s = (data.get("summary") or {}).get(code)
        return s.get("wbillQty") if s else None
    y = date_str[0:4]
    days = read_json("days-%s.json" % y)
    if days and date_str in days:
        s = (days[date_str].get("summary") or {}).get(code)
        return s.get("wbillQty") if s else None
    return None


def find_base_date(target_date_str, back_days, limit=9):
    """找 <= target-back_days 的最近可用交易日（本地优先，其次官网探测）。"""
    td = datetime.date(int(target_date_str[0:4]), int(target_date_str[5:7]), int(target_date_str[8:10]))
    for i in range(limit):
        d = td - datetime.timedelta(days=back_days + i)
        ds = d.strftime("%Y-%m-%d")
        if local_total("lc", ds) is not None:
            return ds
    for i in range(limit):
        d = td - datetime.timedelta(days=back_days + i)
        gd = d.strftime("%Y%m%d")
        if probe_date(gd):
            return d.strftime("%Y-%m-%d")
    return None


def main():
    args = sys.argv[1:]
    date_arg = None
    dry_run = "--dry-run" in args
    if "--date" in args:
        i = args.index("--date")
        if i + 1 < len(args):
            date_arg = args[i + 1]

    base = read_json("data.json")

    if date_arg:
        gd = date_arg
        if not probe_date(gd):
            log("指定日期 %s 在官网没有仓单数据（可能非交易日或尚未公布）。" % gd)
            sys.exit(1)
    else:
        gd = find_latest()
        if not gd:
            log("未能在官网找到已公布的最新仓单数据，请稍后重试或检查网络。")
            sys.exit(1)

    date_str = fmt_date(gd)
    if base and base.get("data_date") == date_str:
        log("本地已是最新（%s），无需更新。" % date_str)
        return 0

    log("发现官网最新仓单数据：%s，开始抓取…" % date_str)
    day = fetch_day(gd)
    if not any(d.get("rows") for d in day.values()):
        log("抓取失败：官网返回空明细。")
        sys.exit(1)

    # 周/月基准
    week_base = find_base_date(date_str, 7)
    month_base = find_base_date(date_str, 28)
    log("周对比基准：%s；月对比基准：%s" % (week_base or "无", month_base or "无"))

    # 组装明细与汇总
    details = {}
    summary = {}
    for code, info in day.items():
        rows = []
        for r in info["rows"]:
            last = r.get("lastWbillQty") or 0
            today = r.get("wbillQty") or 0
            diff = r.get("diff")
            if diff is None:
                diff = today - last
            reg = logout = 0
            if diff > 0:
                reg = diff
            elif diff < 0:
                logout = -diff
            rows.append({
                "warehouse": r["whAbbr"],
                "trademark": r.get("trademarkName") or "",
                "last": last, "today": today, "diff": diff,
                "reg": reg, "logout": logout,
            })
        details[code] = rows
        week_total = local_total(code, week_base)
        month_total = local_total(code, month_base)
        if week_total is None and week_base:
            try:
                wj = api_get(week_base.replace("-", ""), code)
                week_total = next(
                    (x.get("wbillQty") for x in (wj.get("data") or [])
                     if not x.get("whAbbr") and x.get("variety") == "总计"), None)
            except Exception:
                pass
        if month_total is None and month_base:
            try:
                mj = api_get(month_base.replace("-", ""), code)
                month_total = next(
                    (x.get("wbillQty") for x in (mj.get("data") or [])
                     if not x.get("whAbbr") and x.get("variety") == "总计"), None)
            except Exception:
                pass
        today_total = sum(r["today"] for r in rows)
        summary[code] = {
            "variety": info["name"], "code": info["code"],
            "lastWbillQty": sum(r["last"] for r in rows),
            "regWbillQty": sum(r["reg"] for r in rows),
            "logoutWbillQty": sum(r["logout"] for r in rows),
            "wbillQty": today_total,
            "diff": sum(r["diff"] for r in rows),
            "weekDiff": (today_total - week_total) if week_total is not None else None,
            "monthDiff": (today_total - month_total) if month_total is not None else None,
            "weekBaseDate": week_base or None,
            "monthBaseDate": month_base or None,
            "flowInferred": True,
        }

    log("—— 抓取结果预览 ——")
    for code in ["lc", "ps", "si"]:
        s = summary[code]
        wd = "无" if s["weekDiff"] is None else ("%+d" % s["weekDiff"])
        md = "无" if s["monthDiff"] is None else ("%+d" % s["monthDiff"])
        log("%s(%s)：今日 %s 手 | 昨日 %s | 日变化 %+d | 周 %s | 月 %s"
            % (s["variety"], s["code"], s["wbillQty"], s["lastWbillQty"], s["diff"], wd, md))
    if dry_run:
        log("dry-run 模式：不写文件。")
        return 0

    # 历史序列与可用日期
    history = [dict(h) for h in (base or {}).get("history") or []]
    if not history:
        for y in ["2023", "2024", "2025", "2026"]:
            days = read_json("days-%s.json" % y)
            if not days:
                continue
            for d, snap in sorted(days.items()):
                s = snap.get("summary") or {}
                history.append({"date": d,
                                "lc": (s.get("lc") or {}).get("wbillQty") or 0,
                                "ps": (s.get("ps") or {}).get("wbillQty") or 0,
                                "si": (s.get("si") or {}).get("wbillQty") or 0})
    hist_entry = {"date": date_str,
                  "lc": summary["lc"]["wbillQty"],
                  "ps": summary["ps"]["wbillQty"],
                  "si": summary["si"]["wbillQty"]}
    hi = next((i for i, h in enumerate(history) if h["date"] == date_str), None)
    if hi is not None:
        history[hi] = hist_entry
    else:
        history.append(hist_entry)
    history.sort(key=lambda h: h["date"])

    avail = set((base or {}).get("available_dates") or [])
    avail.add(date_str)
    available_dates = sorted(avail, reverse=True)

    day_snap = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": date_str,
        "data_date_raw": gd,
        "week_base_date": week_base or None,
        "month_base_date": month_base or None,
        "summary": summary,
        "details": details,
        "source": SOURCE,
    }
    new_base = dict(day_snap)
    new_base["history"] = history
    new_base["available_dates"] = available_dates
    new_base["day_files"] = (base or {}).get("day_files") or ["days-2024.json", "days-2025.json", "days-2026.json"]

    if base is None:
        log("警告：未找到本地 data.json，将创建全新数据文件（历史序列仅含本次抓取）。")

    write_json("data.json", new_base)
    days_file = "days-%s.json" % date_str[0:4]
    days_map = read_json(days_file) or {}
    days_map[date_str] = day_snap
    write_json(days_file, days_map)

    log("已写入 data.json 与 %s。" % days_file)

    # 重新构建内嵌最新数据的 index.html（无 _src 源码时跳过——线上站点直接读 data.json）
    if not os.path.exists(os.path.join(BASE, "_src", "head.html")):
        log("未找到 _src 源码，跳过 index.html 重建（线上站点实时读取 data.json）。")
    else:
        try:
            r = subprocess.run([sys.executable, os.path.join(BASE, "build.py")],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                log("已重新构建 index.html（内嵌 %s 数据）。" % date_str)
            else:
                log("index.html 重建失败：%s" % (r.stderr or r.stdout)[:300])
        except Exception as e:
            log("index.html 重建失败：%s" % e)

    log("更新完成。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
