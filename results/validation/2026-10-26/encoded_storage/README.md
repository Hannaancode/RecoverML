# Excluded integration evidence

The Windows smoke run contains one Iris/linear history and is excluded from all full-study statistics. It ran before the source commit; its audit explicitly used --preflight and therefore does not certify Git identity. Its source snapshot, actual encoded objects and every request are preserved. The full cloud workflow must pass the strict source-bound audit without that flag.
