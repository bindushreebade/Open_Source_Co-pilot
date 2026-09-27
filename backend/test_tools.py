from app.tools.search import search_code
from app.repository.manager import RepositoryManager


manager = RepositoryManager()

# Use the actual repository path
repository_path = manager.repositories_path + "/Hello-World"

print("Searching in:")
print(repository_path)

print("\nFiles in repository:")

files = manager.list_files(repository_path)

for file in files:
    print(file)

print("\nSearching for README...")

results = search_code(
    repository_path,
    "README"
)

print("\nResults:")

for result in results:
    print(result)

print("\nDone.")