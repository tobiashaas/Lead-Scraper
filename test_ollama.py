"""
Einfacher Ollama Test
"""

import ollama

print("🤖 Testing Ollama...")
print()

try:
    # Test mit einfachem Prompt
    # Test mit llama3.2:latest
    print("Testing model: llama3.2:latest")
    response = ollama.chat(
        model='llama3.2:latest',
        messages=[{
            'role': 'user',
            'content': 'Extract company name from: "Kunze & Ritter GmbH is a company in Stuttgart"'
        }],
        options={
            'num_ctx': 2048,  # Kleinerer Context
            'temperature': 0.1
        }
    )
    
    print("✅ Ollama funktioniert!")
    print()
    print("Response:")
    print(response['message']['content'])
    
except Exception as e:
    print(f"❌ Fehler: {e}")
    import traceback
    traceback.print_exc()
