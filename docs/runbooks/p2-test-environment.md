# P2 测试环境整理

> 目标：让本地验证、W7 服务器彩排前置检查使用同一套命令，避免 pytest 临时目录和缓存污染工作区。

## pytest 默认策略

`pyproject.toml` 已固定：

```text
--basetemp=.tmp/pytest-basetemp -p no:cacheprovider
```

含义：

- pytest 临时目录统一落在 `.tmp/pytest-basetemp`。
- 不生成 `.pytest_cache`。
- 现有 `asyncio_mode = "auto"` 保持不变。

## P2 focused 检查

```powershell
& '.tmp\test-venv\Scripts\python.exe' -m pytest `
  tests/api/test_ui.py `
  tests/core/test_judge_prompt.py `
  tests/core/test_report_files.py `
  tests/test_pytest_config.py `
  -q
```

## 文档编码检查

```powershell
python scripts/check_doc_encoding.py
```

## W7 前置 smoke 建议

```powershell
python -m compileall -q skillhub_eval tests
& '.tmp\test-venv\Scripts\python.exe' -m pytest tests/api/test_ui.py tests/api/test_conversations_upload.py -q
```
