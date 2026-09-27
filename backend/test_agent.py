from app.agent.agent import IssueAnalyzer


analyzer = IssueAnalyzer()


result = analyzer.analyze(
    title="Reminder API returns 500 when expiresAt is null",

    description="""
    The reminder API returns HTTP 500 when expiresAt
    is not provided in the request.
    """,

    comments=[]
)


print("\nAI ANALYSIS:\n")

print(result)