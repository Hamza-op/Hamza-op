import os
import re
import json
import urllib.request
import subprocess
import shutil
import stat

USER = "Hamza-op"
EXTENSIONS = {'.rs', '.ts', '.tsx', '.py', '.js', '.sh', '.cpp', '.h', '.css', '.html'}
EXCLUDE_DIRS = {'node_modules', 'target', 'dist', 'build', '.git', '.github', 'temp_stats_clone'}

def robust_rmtree(path):
    """Robust rmtree that overrides Windows read-only file permissions to cleanly delete git repositories."""
    if not os.path.exists(path):
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                os.chmod(file_path, stat.S_IWRITE)
                os.unlink(file_path)
            except Exception:
                pass
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            try:
                os.chmod(dir_path, stat.S_IWRITE)
                os.rmdir(dir_path)
            except Exception:
                pass
    try:
        os.chmod(path, stat.S_IWRITE)
        os.rmdir(path)
    except Exception:
        pass

def fetch_repos(token=None):
    url = f"https://api.github.com/users/{USER}/repos?per_page=100"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    if token:
        req.add_header("Authorization", f"token {token}")
        
    try:
        with urllib.request.urlopen(req) as response:
            repos = json.loads(response.read().decode())
            # Filter out forks and the profile repository itself (since it's mostly markdown)
            return [repo for repo in repos if not repo['fork'] and repo['name'].lower() != USER.lower()]
    except Exception as e:
        print(f"Error fetching repos: {e}")
        return []

def count_lines(repo_url, repo_name):
    temp_dir = os.path.abspath(f"temp_stats_clone_{repo_name}")
    if os.path.exists(temp_dir):
        robust_rmtree(temp_dir)
        
    # Clone repository with depth 1
    print(f"Cloning {repo_name}...")
    try:
        subprocess.run(["git", "clone", "--depth", "1", repo_url, temp_dir], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Failed to clone {repo_name}: {e}")
        return 0, 0
        
    total_loc = 0
    rust_loc = 0
    
    for root, dirs, files in os.walk(temp_dir):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in EXTENSIONS:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = sum(1 for _ in f)
                        total_loc += lines
                        if ext == '.rs':
                            rust_loc += lines
                except Exception as e:
                    # Ignore unreadable files
                    pass
                    
    # Cleanup clone
    if os.path.exists(temp_dir):
        robust_rmtree(temp_dir)
        
    return total_loc, rust_loc

def main():
    token = os.environ.get("GITHUB_TOKEN")
    repos = fetch_repos(token)
    
    if not repos:
        print("No repositories found to process.")
        return
        
    total_loc = 0
    total_rust_loc = 0
    repo_count = len(repos)
    
    print(f"Found {repo_count} original repositories.")
    
    for repo in repos:
        repo_name = repo['name']
        repo_url = repo['clone_url']
        if token:
            repo_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
            
        loc, rust_loc = count_lines(repo_url, repo_name)
        print(f"-> {repo_name}: {loc} LOC (Rust: {rust_loc})")
        total_loc += loc
        total_rust_loc += rust_loc
        
    print(f"\nSummary:")
    print(f"Total Lines of Code: {total_loc}")
    print(f"Total Rust Lines: {total_rust_loc}")
    print(f"Total Repositories: {repo_count}")
    
    # Calculate percentage
    rust_pct = (total_rust_loc / total_loc * 100) if total_loc > 0 else 0
    
    # Read README.md
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        print("README.md not found in root.")
        return
        
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. Update Badge
    badge_start = "<!-- LOC_BADGE_START -->"
    badge_end = "<!-- LOC_BADGE_END -->"
    badge_pattern = re.escape(badge_start) + r".*?" + re.escape(badge_end)
    new_badge = f'{badge_start}<img src="https://img.shields.io/badge/Total_Lines_of_Code-{total_loc:,}-6366f1?style=flat-square&labelColor=0f172a" />{badge_end}'
    content = re.sub(badge_pattern, new_badge, content, flags=re.DOTALL)
    
    # 2. Update Metrics Board
    board_start = "<!-- METRICS_BOARD_START -->"
    board_end = "<!-- METRICS_BOARD_END -->"
    board_pattern = re.escape(board_start) + r".*?" + re.escape(board_end)
    new_board = f"""{board_start}
<div align="center">
  <table border="0" cellspacing="0" cellpadding="10">
    <tr>
      <td>💻 <strong>Total Source Lines of Code:</strong> <code>{total_loc:,}</code></td>
      <td>🦀 <strong>Systems Code (Rust):</strong> <code>{total_rust_loc:,} LOC ({rust_pct:.1f}%)</code></td>
      <td>📂 <strong>Indexed Repositories:</strong> <code>{repo_count}</code></td>
    </tr>
  </table>
</div>
{board_end}"""
    content = re.sub(board_pattern, new_board, content, flags=re.DOTALL)
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("README.md updated successfully!")

if __name__ == "__main__":
    main()
