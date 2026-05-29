# Jira 任务分析器

定期分析 KAT-10938 子任务，统计未处理的项目。

## 安装

```bash
cd /Users/zhiyong/工作/jira-analyzer
pip install -r requirements.txt
```

## 配置

1. 编辑 `config.json`
2. 填写你的 Jira API Token: https://id.atlassian.net/manage-profile/security/api-tokens

## 运行

```bash
python jira_analyzer.py
```

会自动生成报告并在浏览器中打开。

## 定时运行 (macOS)

编辑 crontab:
```bash
crontab -e
```

添加每天早上 9 点运行:
```
0 9 * * * cd /Users/zhiyong/工作/jira-analyzer && /usr/local/bin/python3 jira_analyzer.py
```

## 定时运行 (使用 launchd，推荐)

创建 `~/Library/LaunchAgents/com.jira.analyzer.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jira.analyzer</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/zhiyong/工作/jira-analyzer/jira_analyzer.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/zhiyong/工作/jira-analyzer/output/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/zhiyong/工作/jira-analyzer/output/scheduler-error.log</string>
</dict>
</plist>
```

加载:
```bash
launchctl load ~/Library/LaunchAgents/com.jira.analyzer.plist
```

卸载:
```bash
launchctl unload ~/Library/LaunchAgents/com.jira.analyzer.plist
```
