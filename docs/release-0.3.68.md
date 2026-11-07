# DWho 0.3.68

Enumerate matching Redis keys with incremental SCAN.

The Redis adapter requires Redis 2.8 or later for `keys()`. It retains its
server-name-to-list return format and pattern and prefix filters. SCAN can see
changes made during a traversal. Duplicate keys are removed from each result.
