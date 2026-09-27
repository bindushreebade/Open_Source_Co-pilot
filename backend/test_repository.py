from app.repository.manager import RepositoryManager


manager = RepositoryManager()


repository_url = "neomjs/neo"


result = agent.run(
    owner="neomjs",
    repo="neo",
    issue_number=17438,
    repository_path=repository_path
)

repository_path = result["path"]

print(result)


files = manager.list_files(
    repository_path
)

print("\nFiles:")

for file in files:
    print(file)


# Read README
if "README" in files:

    content = manager.read_file(
        repository_path,
        "README"
    )

    print("\nREADME CONTENT:")
    print(content)
