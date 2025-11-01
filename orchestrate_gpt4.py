#!/usr/bin/env python3
"""
Orchestration script to invoke GPT-4 for code generation.
"""

import os
from openai import OpenAI

# Initialize OpenAI client (API key and base URL are pre-configured in environment)
client = OpenAI()

def invoke_gpt4_coder(task_file_path, output_dir):
    """
    Invoke GPT-4 to generate code based on a task specification.
    """
    # Read the task specification
    with open(task_file_path, 'r') as f:
        task_spec = f.read()
    
    # Create the prompt for GPT-4
    prompt = f"""You are an expert Python developer implementing a critical system component.

{task_spec}

Please provide the complete implementation for all requested files. For each file, use the following format:

```filename: path/to/file.py
[file content here]
```

Make sure to:
1. Include all necessary imports
2. Use proper type hints
3. Add comprehensive docstrings
4. Follow PEP 8 style guidelines
5. Include error handling where appropriate

Generate the code now."""

    print("🤖 Invoking GPT-4 for code generation...")
    print(f"📋 Task: {task_file_path}")
    
    # Invoke GPT-4
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are an expert Python developer who writes clean, well-documented, production-quality code."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=16000
    )
    
    # Extract the generated code
    generated_code = response.choices[0].message.content
    
    # Save the raw response
    response_file = os.path.join(output_dir, "gpt4_response.md")
    with open(response_file, 'w') as f:
        f.write(generated_code)
    
    print(f"✅ GPT-4 response saved to: {response_file}")
    print(f"📊 Tokens used: {response.usage.total_tokens}")
    
    return generated_code

if __name__ == "__main__":
    task_file = "/home/ubuntu/rcrag-service/TASK_DAY1-2_GPT4.md"
    output_dir = "/home/ubuntu/rcrag-service"
    
    result = invoke_gpt4_coder(task_file, output_dir)
    print("\n✨ Code generation complete!")
