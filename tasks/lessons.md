# Lessons Learned

## 2026-02-27: deploy.py に ⏺ マーカー混入
- **問題**: Claude Code がファイルを Write ツールで作成した際、出力マーカー `⏺` (U+23FA) が先頭行に混入し、Pi 上で SyntaxError になった
- **対策**: リモートマシンにファイルを作成/編集した後は、必ず `python3 -c 'import py_compile; py_compile.compile("file.py", doraise=True)'` で構文チェックする
- **教訓**: Write ツールの出力内容にマーカー文字が含まれていないか注意する
