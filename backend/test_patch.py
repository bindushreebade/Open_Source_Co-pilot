from app.tools.repository import apply_patch

repository_path = (
    r"D:\AI-Agent-Software-Engineer"
    r"\AI-Agent-Software-Engineer"
    r"\repositories\neo"
)

old_text = (
    "req.batch->remaining_tiles.fetch_sub("
    "1, std::memory_order_relaxed) - 1;"
)

new_text = (
    "req.batch->remaining_tiles.fetch_sub("
    "1, std::memory_order_acq_rel) - 1;"
)

result = apply_patch(
    repository_path,
    "csrc/storage_backends/connector_base.h",
    old_text,
    new_text
)

print(result)
