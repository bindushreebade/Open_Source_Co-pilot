from app.repository.manager import RepositoryManager
from app.repository.search import CodeSearcher


manager = RepositoryManager()
searcher = CodeSearcher()


repository_url = "https://github.com/octocat/Hello-World.git"


result = manager.clone_repository(
    repository_url
)

repository_path = result["path"]


results = searcher.search(
    repository_path,
    "hello"
)


print("\nSEARCH RESULTS:\n")

for result in results:

    print(
        f"{result['file']} "
        f"(line {result['line']}) "
        f"-> {result['match']}"
    )