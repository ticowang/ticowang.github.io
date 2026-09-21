@echo off
rem ============================================================
rem  安装“广期所仓单日报自动更新”计划任务
rem  效果：每天 07:45（官网公布后）自动从广期所官网抓取最新仓单数据，
rem        更新 data.json / days-*.json 并重建 index.html。
rem  注意：需要管理员权限运行一次（右键“以管理员身份运行”）。
rem ============================================================
chcp 65001 >nul
schtasks /Create /TN "GFEX仓单日报自动更新" /TR "cmd /c cd /d ""%~dp0"" && python update_gfex.py" /SC DAILY /ST 07:45 /F
if %errorlevel%==0 (
    echo.
    echo [成功] 已注册计划任务：每天 07:45 自动更新仓单数据。
    echo        任务名：GFEX仓单日报自动更新
    echo        查看方式：任务计划程序 - 任务计划程序库 - GFEX仓单日报自动更新
    echo        更新日志：update_log.txt
) else (
    echo.
    echo [失败] 注册未成功，请右键本脚本选择“以管理员身份运行”后再试。
)
echo.
pause
