#!/usr/bin/env python3
"""
Extract files from GPT-4's markdown response.
"""

import re
import os

def extract_files_from_markdown(md_content, output_base_dir):
    """
    Parse markdown content and extract code blocks into files.
    """
    # Pattern to match: ```filename: path/to/file.ext
    pattern = r'```filename:\s*([^\n]+)\n(.*?)```'
    matches = re.findall(pattern, md_content, re.DOTALL)
    
    extracted_files = []
    
    for filename, content in matches:
        filename = filename.strip()
        filepath = os.path.join(output_base_dir, filename)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Write the file
        with open(filepath, 'w') as f:
            f.write(content)
        
        extracted_files.append(filepath)
        print(f"✅ Extracted: {filepath}")
    
    return extracted_files

if __name__ == "__main__":
    response_file = "/home/ubuntu/rcrag-service/gpt4_response.md"
    output_dir = "/home/ubuntu/rcrag-service"
    
    with open(response_file, 'r') as f:
        content = f.read()
    
    files = extract_files_from_markdown(content, output_dir)
    print(f"\n📦 Extracted {len(files)} files total")
