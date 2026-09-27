import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_code",
                description="Search code in a repository.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string"
                        }
                    },
                    "required": ["query"]
                }
            )
        ]
    )
]


response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Search the repository for handle_tile_completion.",
    config=types.GenerateContentConfig(
        tools=tools,
        temperature=0.2
    )
)

print(response.text)
print(response.function_calls)