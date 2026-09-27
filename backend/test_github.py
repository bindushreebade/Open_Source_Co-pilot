from app.github.client import GitHubClient


client = GitHubClient()

owner = "facebook"
repo = "react"


# Test repository
repository = client.get_repository(owner, repo)

print("Repository:")
print(repository.full_name)


# Test issue
issue = client.get_issue(
    owner,
    repo,
    1
)

print("\nIssue:")
print(issue)


# Test files
files = client.list_files(owner, repo)

print("\nRepository files:")

for file in files:
    print(file["path"])