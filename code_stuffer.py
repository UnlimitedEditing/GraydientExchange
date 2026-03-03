import os

def bundle_python_files(output_file="CodeBundle.txt"):
    root_dir = os.getcwd()
    python_files = []

    # 1. Collect all .py files recursively
    for root, dirs, files in os.walk(root_dir):
        # Optional: Skip common folders you don't want to scan
        if any(x in root for x in ['venv', '.git', '__pycache__']):
            continue
            
        for file in files:
            if file.endswith(".py") and file != "bundle_code.py":
                full_path = os.path.join(root, file)
                # Store relative path for the index
                rel_path = os.path.relpath(full_path, root_dir)
                python_files.append((full_path, rel_path))

    with open(output_file, "w", encoding="utf-8") as f:
        # 2. Write the Index/Structure
        f.write("CODEBASE BUNDLE REPORT\n")
        f.write("=" * 50 + "\n")
        f.write("PROJECT STRUCTURE:\n")
        for _, rel_path in python_files:
            f.write(f" - {rel_path}\n")
        f.write("\n" + "=" * 50 + "\n\n")

        # 3. Append the Content
        for full_path, rel_path in python_files:
            f.write(f"FILE: {rel_path}\n")
            f.write("-" * 50 + "\n")
            try:
                with open(full_path, "r", encoding="utf-8") as code_file:
                    f.write(code_file.read())
            except Exception as e:
                f.write(f"[Error reading file: {e}]")
            f.write("\n\n" + "# " + "="*20 + " END OF FILE " + "="*20 + "\n\n")

    print(f"Success! Bundled {len(python_files)} files into {output_file}")

if __name__ == "__main__":
    bundle_python_files()
