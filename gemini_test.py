import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-flash-latest")
# for m in genai.list_models():
#     print(m.name)
prompt = """
You are an investment assistant for trading Pokemon cards.
Given the following info:
- Recent price: 12.49
- Old price: 13.27
- Trend: -5.9%
- Decision: SELL

Explain in plain English whether the user should hold or sell, and why.
"""

response = model.generate_content(prompt)
print(response.text)
