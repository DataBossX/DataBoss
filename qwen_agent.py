# qwen_agent.py
import os
import openai  # Can swap with qwen API or ollama subprocess
from github import Github
from dotenv import load_dotenv

load_dotenv()

# --- Prompt Qwen ---
def ask_qwen(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",  # Replace with 'qwen' if using another client
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# --- Save file locally ---
def save_code(filename, content):
    path = os.path.join("generated", filename)
    os.makedirs("generated", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Saved: {path}")
    return path

# --- Commit to GitHub ---
def commit_to_github(local_file, repo_path):
    token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPO")
    g = Github(token)
    repo = g.get_repo(repo_name)

    with open(local_file, "r", encoding="utf-8") as file:
        content = file.read()

    try:
        contents = repo.get_contents(repo_path)
        repo.update_file(contents.path, "Qwen auto-update", content, contents.sha)
    except Exception:
        repo.create_file(repo_path, "Qwen auto-create", content)
    print(f"🚀 Pushed {repo_path} to GitHub")

# --- MAIN ---
if __name__ == "__main__":
    prompt = input("Enter your Qwen prompt:\n> ")
    code = ask_qwen(prompt)
    file_path = save_code("qwen_output.py", code)
    commit_to_github(file_path, "qwen_output.py")
