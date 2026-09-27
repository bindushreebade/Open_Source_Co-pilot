from app.repository.manager import RepositoryManager
from app.tools.repository import read_file
from app.tools.search import search_code

manager = RepositoryManager()

repository_path = r"D:\AI-Agent-Software-Engineer\AI-Agent-Software-Engineer\repositories\neo"

print("\n=== Searching handle_tile_completion ===")

results = search_code(
    repository_path,
    "handle_tile_completion",
    "csrc/storage_backends",
    20
)

for result in results:
    print(result)

print("\n=== Reading relevant function ===")

content = read_file(
    repository_path,
    "csrc/storage_backends/connector_base.h",
    580,
    660
)

print(content)
